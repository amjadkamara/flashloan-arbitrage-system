import logging
import colorlog
import sys
from typing import Optional, Dict, Any
from pathlib import Path

# Custom formatter with colors
class ColoredFormatter(colorlog.ColoredFormatter):
    """Custom colored formatter with improved formatting"""
    
    def __init__(self):
        super().__init__(
            "%(log_color)s%(asctime)s | %(levelname)8s | %(name)20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Get a configured logger with colored output
    
    Args:
        name: Logger name
        level: Logging level
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        return logger
    
    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Create colored formatter
    formatter = ColoredFormatter()
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    return logger

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Setup and configure a logger with colored output
    (Alias for get_logger for backward compatibility)
    """
    return get_logger(name, level)

# Alias for backward compatibility
setup_logging = setup_logger
