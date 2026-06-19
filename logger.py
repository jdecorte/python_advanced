import logging
from logging.handlers import RotatingFileHandler

class Logger:
    def __init__(self, name="log", log_file="logger.log", level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )

            console = logging.StreamHandler()
            console.setFormatter(formatter)

            file_handler = RotatingFileHandler(
                log_file, maxBytes=1_000_000, backupCount=3
            )
            file_handler.setFormatter(formatter)

            self.logger.addHandler(console)
            self.logger.addHandler(file_handler)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)