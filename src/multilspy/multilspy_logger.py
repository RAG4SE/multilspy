"""
Multilspy logger module.
"""
import inspect
import json
import logging
from datetime import datetime
from typing_extensions import TypedDict

class LogLine(TypedDict):
    """
    Represents a line in the Multilspy log
    """

    time: str
    level: str
    caller_file: str
    caller_name: str
    caller_line: int
    message: str

class MultilspyLogger:
    """
    Logger class
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("multilspy")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
        self.logger.propagate = False

    def log(self, debug_message: str, level: int, sanitized_error_message: str = "") -> None:
        """
        Log the debug and santized messages using the logger
        """

        debug_message = debug_message.replace("'", '"').replace("\n", " ")
        sanitized_error_message = sanitized_error_message.replace("'", '"').replace("\n", " ")

        self.logger.log(level=level, msg=debug_message)
