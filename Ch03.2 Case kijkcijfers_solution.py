import datetime
import pytz
import time
import os
import sys
import requests
import json
import numpy as np
import pandas as pd 
import openmeteo_requests
import requests_cache
from retry_requests import retry

from langchain_groq import ChatGroq
from dotenv import load_dotenv, find_dotenv
from logger import Logger

load_dotenv(find_dotenv(usecwd=True))

scrape = True
genre_prediction = True
weather_history = True
debug = True

class Data:
    """Base class for data handling. This class provides common functionality for loading, saving, and processing data. 
    It is intended to be subclassed by specific data types (e.g., KijkCijfers, Genre, Weather) 
    that will implement their own data-specific methods."""
    def __init__(self,logger:Logger):
        self.records = [] # list of dictionaries
        self.logger = logger

    def create_df(self):
        self.df = pd.DataFrame(self.records)
        self.logger.info(f"DataFrame created with {len(self.df)} records.")
  
    def load_df(self):
        self.df = pd.read_csv(self.csv,sep=";")

    def save_df(self):
        self.df.to_csv(self.csv, index=False, sep=";")
        self.logger.info(f"Data saved to {self.csv}")

    def my_name(self):
        if debug: # print the name of the calling function
            self.logger.info(f"Calling {sys._getframe(1).f_code.co_name}")

class KijkCijfers(Data):
    def __init__(self, start_date, end_date,logger:Logger):
        super().__init__(logger)  
        self.start_date = start_date
        self.end_date = end_date
        self.url = "https://api.cim.be/api/cim_tv_public_results_daily_views?dateDiff={date}&reportType=north"
        self.csv = "kijkcijfers.csv"

    def scrape_data(self):
        current_date = self.start_date
        while current_date <= self.end_date:
            year = current_date.year
            date_str = current_date.strftime("%Y-%m-%d")
            current_url = self.url.format(date=date_str)
            self.logger.info(f"Fetching data for {date_str}...")
            try:
                response = requests.get(current_url)
                if response.status_code == 200:
                    data = response.json()
                    data = data.get('hydra:member')
                    for item in data:
                        record = {
                            'ranking': item.get('ranking'),
                            'description': item.get('description').upper(),
                            'channel': item.get('channel').upper(),
                            'dateDiff': item.get('dateDiff'),
                            'startTime': item.get('startTime'),
                            'rLength': item.get('rLength'),
                            'rateInk': item.get('rateInK')
                        }
                        for key in record:
                            val = record[key]
                            if type(val) == str:
                                record[key] = val.replace('"', '')  # remove double quotes

                        if len(record['description']) > 0: # only keep records with a description
                            self.records.append(record)
                else:
                    self.logger.error(f"Request failed with status code {response.status_code}")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"An error occurred: {e}")
            current_date += datetime.timedelta(days=1)

    def clean_data(self):
        return
    
    def convert_names(self):
        conversion_table = {
            "VIER": "PLAY4",
            "EEN": "VRT 1",
            "CANVAS": "VRT CANVAS",
            "Q2": "VTM2",
            "VITAYA": "VTM3",
            "CAZ": "VTM4",
            "ELEVEN PRO LEAGUE 1 NL":"DAZN PRO LEAGUE 1 (NL)"
        }
        convert = lambda x: conversion_table[x] if x in conversion_table else x
        self.df['channel'] = self.df['channel'].apply(convert) 

class Genre(Data):
    def __init__(self,kijkcijfers_df,logger:Logger):
        super().__init__(logger)
        self.my_name()
        self.csv = "genres.csv"

        # self.records = [] # list of dictionaries
        self.kijkcijfers_df = kijkcijfers_df
        self.df = None
        self.count = 0

        self.genres = [
            "Actualiteiten en nieuws",
            "Talkshow",
            "Reality-tv",
            "Fictie (drama)",
            "Comedy",
            "Quiz",
            "Spelprogramma",
            "Documentaire",
            "Human interest",
            "Lifestyle",
            "Kookprogramma",
            "Reisprogramma",
            "Woon- en renovatieprogramma",
            "Datingprogramma",
            "Talentenshow",
            "Muziekprogramma",
            "Jeugdprogramma",
            "Sport",
            "Misdaad (crime)",
            "Soap",
            "Telenovelle",
            "Historisch programma",
            "Natuurprogramma",
            "Wetenschap en technologie",
            "Cultuurprogramma",
            "Religieus programma",
            "Satire"
        ]

        MODEL_NAME = 'llama-3.3-70b-versatile'
        self.model = ChatGroq(model_name=MODEL_NAME,
                        temperature=0.5, # controls creativity
                        api_key=os.getenv('GROQ_API_KEY'))

    def predict_genres(self):
        self.my_name()
        # Create a set to track unique (channel, program) combinations
        # unique_combinations = set()
        # buffer = []
        for index, row in self.kijkcijfers_df.iterrows():
            try:
                channel = row['channel']
                program = row['description']

                # check if the combination is already in self.records
                if any(record['channel'] == channel and record['program'] == program for record in self.records):
                    continue

                question = f"Wat is het genre van het Vlaamse Tv-programma {program} op de zender {channel}? Beperk je antwoord tot één element uit de volgende lijst: " 
                question += ", ".join(self.genres) 
                question += " Herhaal de vraag NIET in je antwoord. Geef enkel het genre terug, zonder extra uitleg of context."  
                res = self.model.invoke(question)
                # find out what is in the result
                # res.model_dump()
                genre = res.content
                record = {
                'channel': channel,
                'program': program,
                'genre': genre,
                }
                self.logger.info(f"Predicted genre for {program} on {channel}: {genre}")
                self.records.append(record)

            except Exception as e:
                self.logger.error(f"An error occurred: {e}")
                continue

class Weather(Data):
    def __init__(self,logger:Logger):
        super().__init__(logger)
        # Setup the Open-Meteo API client with cache and retry on error
        self.cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        self.retry_session = retry(self.cache_session, retries = 5, backoff_factor = 0.2)
        self.openmeteo = openmeteo_requests.Client(session = self.retry_session)
        self.csv = "weather.csv"

    def get_weather(self,start_date, end_date):
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": 50.8505,
            "longitude": 2.3488,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "hourly": ["temperature_2m", "precipitation"],
            "timezone": "Europe/Berlin"
        }

        retries = 0
        while retries <= 5:
            try:
                responses = self.openmeteo.weather_api(url, params=params)
                self.logger.info("Weather data fetched successfully.")
                break  # exit the loop
            except Exception as e:
                retries += 1
                self.logger.error(f"An error occurred while fetching weather data: {e}")
                # wait 5 minutes before retrying
                time.sleep(3)

        if retries > 5:
            self.logger.error("No weather data received.")
            return

        # Process first location. Add a for-loop for multiple locations or weather models
        response = responses[0]

        # Process hourly data. The order of variables needs to be the same as requested.
        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_precipitation = hourly.Variables(1).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
            start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
            end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = hourly.Interval()),
            inclusive = "left"
        )}

        hourly_data["temperature_2m"] = hourly_temperature_2m
        hourly_data["precipitation"] = hourly_precipitation

        self.df = pd.DataFrame(data = hourly_data)
        # print(self.df)

def main():
    logger = Logger(name="KijkCijfers", log_file="kijkcijfers.log")
    start_date = datetime.date.today() - datetime.timedelta(days=35)
    end_date = datetime.date.today() - datetime.timedelta(days=33)
    
    kijkcijfers = KijkCijfers(start_date, end_date,logger)
    logger.info(f"Start date: {kijkcijfers.start_date}")
    logger.info(f"End date: {kijkcijfers.end_date}")
    if scrape:
        kijkcijfers.scrape_data()
        kijkcijfers.create_df()
        kijkcijfers.clean_data()
        kijkcijfers.convert_names()
        kijkcijfers.save_df()
    else:  # postprocessing
        kijkcijfers.load_df()
        kijkcijfers.convert_names()
        kijkcijfers.save_df()

    if genre_prediction:
        genre = Genre(kijkcijfers.df, logger)
        genre.predict_genres()
        logger.info(f"Aantal programma's = {genre.count}")
        genre.create_df()
        genre.save_df()

    if weather_history:
        weather = Weather(logger)
        weather.get_weather(start_date, end_date)
        weather.save_df()
   
if __name__ == "__main__":
    main()
