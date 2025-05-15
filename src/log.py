"""Output infos during running."""
import datetime
import os
import sys

from loguru import logger as logger_

from src.config import settings

DIR_LOGS = settings.filepath.root / settings.filepath.data / "logs"
os.makedirs(DIR_LOGS, exist_ok=True)

logger_.remove()
logger_.add(sink=sys.stdout, format=settings.project.log_format, colorize=True, level=settings.project.log_level)
logger_.add(sink=DIR_LOGS / f'{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.log', format=settings.project.log_format, colorize=False, level="INFO", encoding='utf-8')
logger_.add(sink=DIR_LOGS / f'{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.debug', format=settings.project.log_format, colorize=False, level="DEBUG", encoding='utf-8')

logger = logger_

__all__ = ["logger"]
