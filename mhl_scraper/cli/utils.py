import sys
import logging
from typing import Optional

def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """
    Configure logging for the MHL scraper.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO
        log_file: Optional path to log file. If provided, logs will also be written to file.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger for mhl_scraper package
    root_logger = logging.getLogger('mhl_scraper')
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []

    # Add console handler (only for verbose mode to avoid cluttering CLI output)
    if verbose:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Add file handler if log_file specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(f"Logging to file: {log_file}")
