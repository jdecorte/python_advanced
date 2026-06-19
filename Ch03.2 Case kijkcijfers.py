import datetime
import pytz
import time
import os
import sys
import requests
import json
import numpy as np
import pandas as pd 
from google import genai
import openmeteo_requests
import requests_cache
from retry_requests import retry

scrape = False
genre_prediction = True
weather_history = False
debug = False

class Data:
    """Base class for data handling. This class provides common functionality for loading, saving, and processing data. 
    It is intended to be subclassed by specific data types (e.g., KijkCijfers, Genre, Weather) 
    that will implement their own data-specific methods."""
    def __init__(self):
        self.records = [] # list of dictionaries

    def create_df(self):
        self.df = pd.DataFrame(self.records)
  
    def load_df(self):
        self.df = pd.read_csv(self.csv,sep=";")

    def save_df(self):
        self.df.to_csv(self.csv, index=False, sep=";")

    def my_name(self):
        if debug: # print the name of the calling function
            print (f"Calling {sys._getframe(1).f_code.co_name}")

class KijkCijfers(Data):
    def __init__(self, start_date, end_date):
        super().__init__()  
        self.start_date = start_date
        self.end_date = end_date
        self.url = "https://api.cim.be/api/cim_tv_public_results_daily_views?dateDiff={date}&reportType=north"
        self.csv = "kijkcijfers.csv"

    def scrape_data(self):
        # TODO OPGAVE 1
        return
        
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
    def __init__(self):
        super().__init__()
        # Setup the Open-Meteo API client with cache and retry on error
        self.cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        self.retry_session = retry(self.cache_session, retries = 5, backoff_factor = 0.2)
        self.openmeteo = openmeteo_requests.Client(session = self.retry_session)
        self.csv = "weather.csv"

    def get_weather(self,start_date, end_date):
        # TODO OPGAVE 2
        return

def main():
    logger = Logger(name="KijkCijfers", log_file="kijkcijfers.log")
    start_date = datetime.date.today() - datetime.timedelta(days=35)
    end_date = datetime.date.today() - datetime.timedelta(days=30)
    
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