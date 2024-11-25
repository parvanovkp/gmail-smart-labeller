from pathlib import Path
import logging
import sys
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and emojis for different log levels"""
    
    COLORS = {
        'DEBUG': '\033[38;5;246m',  # Gray
        'INFO': '\033[38;5;39m',    # Blue
        'WARNING': '\033[38;5;208m', # Orange
        'ERROR': '\033[38;5;196m',   # Red
        'CRITICAL': '\033[48;5;196;38;5;231m', # White on Red
    }

    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '📝',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨',
    }

    RESET = '\033[0m'

    def format(self, record):
        # Add emoji and color if it's a terminal
        if sys.stdout.isatty():
            emoji = self.EMOJIS.get(record.levelname, '')
            color = self.COLORS.get(record.levelname, '')
            reset = self.RESET
        else:
            emoji = ''
            color = ''
            reset = ''

        # Format time in a readable way
        record.asctime = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Create the basic message
        message = super().format(record)
        
        # Add colors and emojis for terminal output
        return f"{color}{emoji} {message}{reset}"

def setup_logger(user_config_dir: Path) -> logging.Logger:
    """Setup application logging with singleton pattern"""
    logger_name = 'gmail_smart_labeler'
    
    # Return existing logger if already set up
    if logger_name in logging.root.manager.loggerDict:
        return logging.getLogger(logger_name)
    
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # Only add handlers if they haven't been added yet
    if not logger.handlers:
        # Create logs directory if it doesn't exist
        log_dir = user_config_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        # File handler for complete logging
        log_file = log_dir / f"smart_labeler_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))

        # Console handler with colors and emojis
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter(
            '%(message)s'
        ))

        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger