import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging(log_level=logging.INFO, log_file="app.log"):
    # Get the root logger
    logger = logging.getLogger()
    
    # Debug: Log existing handlers
    logger.debug(f"Existing handlers before setup: {logger.handlers}")
    
    # Clear existing handlers to prevent duplicates
    logger.handlers.clear()
    
    # Set the logging level
    logger.setLevel(log_level)

    # Define the log format
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # Add file handler with rotation
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # Debug: Log handlers after setup
    logger.debug(f"Handlers after setup: {logger.handlers}")
    
    return logger

# Initialize logger once at module level
logger = setup_logging(log_level=logging.DEBUG)