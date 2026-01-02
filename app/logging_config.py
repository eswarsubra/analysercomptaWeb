"""Logging configuration for AnalyzerComptaWeb."""

import logging
from logging.handlers import RotatingFileHandler
import os

# Log file - configurable via environment variable
LOG_FILE = os.environ.get('LOG_PATH', 'analyzercompta.log')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Rollover settings
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Keep 3 backup files


def setup_logging(level=logging.INFO):
    """
    Setup logging with rotating file handler.

    Args:
        level: Logging level (default INFO)
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler (for development)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Suppress noisy asyncio logs on Windows
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    logging.info("Logging initialized - file: %s", os.path.abspath(LOG_FILE))


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
