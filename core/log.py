import logging
import sys
from enum import Enum


class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


logger = logging.getLogger("BillCoector")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(filename)s[:%(lineno)d] - %(message)s"
    ))
logger.addHandler(handler)
logger.setLevel(logging.INFO)
