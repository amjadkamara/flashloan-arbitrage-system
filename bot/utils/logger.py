# bot/utils/logger.py
"""
Colored logging system for the flashloan arbitrage bot.

Provides:
- Colored console output for different log levels
- File logging with rotation
- Structured logging for trading events
- Performance logging for bot operations

Usage:
    from bot.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Bot started successfully")
    logger.warning("Low profit opportunity detected")
    logger.error("Transaction failed")
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json
import os

try:
    from colorama import Fore, Back, Style, init
    COLORAMA_AVAILABLE = True
    init(autoreset=True)  # Initialize colorama
except ImportError:
    COLORAMA_AVAILABLE = False

try:
    from rich.console import Console
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""

    # Color mappings for log levels
    COLORS = {
        'DEBUG': Fore.CYAN if COLORAMA_AVAILABLE else '',
        'INFO': Fore.GREEN if COLORAMA_AVAILABLE else '',
        'WARNING': Fore.YELLOW if COLORAMA_AVAILABLE else '',
        'ERROR': Fore.RED if COLORAMA_AVAILABLE else '',
        'CRITICAL': Fore.RED + Back.YELLOW + Style.BRIGHT if COLORAMA_AVAILABLE else ''
    }

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and COLORAMA_AVAILABLE

        # Define format templates
        self.base_format = "{timestamp} | {level:8} | {name:20} | {message}"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and structure."""

        # Create timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Get color for log level
        level_color = self.COLORS.get(record.levelname, "")
        reset_color = Style.RESET_ALL if self.use_colors and COLORAMA_AVAILABLE else ""

        # Format the message - avoid unicode issues
        message = record.getMessage()
        
        # Replace problematic unicode characters for Windows
        if os.name == 'nt':
            message = message.replace('🚀', '[ROCKET]')
            message = message.replace('⚠️', '[WARNING]')
            message = message.replace('✅', '[SUCCESS]')
            message = message.replace('❌', '[ERROR]')
            message = message.replace('🎯', '[TARGET]')
            message = message.replace('📤', '[SEND]')
            message = message.replace('📊', '[CHART]')
            message = message.replace('⏱️', '[TIMER]')

        # Format the message
        if self.use_colors:
            try:
                formatted_message = (
                    f"{Fore.WHITE if COLORAMA_AVAILABLE else ''}{timestamp}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''} | "
                    f"{level_color}{record.levelname:8}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''} | "
                    f"{Fore.BLUE if COLORAMA_AVAILABLE else ''}{record.name:20}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''} | "
                    f"{level_color}{message}{reset_color}"
                )
            except UnicodeEncodeError:
                # Fallback without colors
                formatted_message = self.base_format.format(
                    timestamp=timestamp,
                    level=record.levelname,
                    name=record.name,
                    message=message
                )
        else:
            formatted_message = self.base_format.format(
                timestamp=timestamp,
                level=record.levelname,
                name=record.name,
                message=message
            )

        # Add exception info if present
        if record.exc_info:
            formatted_message += "\n" + self.formatException(record.exc_info)

        return formatted_message


class TradingLogger:
    """Specialized logger for trading events with structured data."""

    def __init__(self, name: str):
        self.logger = get_logger(f"TRADING.{name}")

    def opportunity_found(self, token_pair: str, profit_pct: float, exchanges: Dict[str, float]):
        """Log arbitrage opportunity detection."""
        self.logger.info(
            f"[TARGET] OPPORTUNITY: {token_pair} | Profit: {profit_pct:.2f}% | "
            f"Prices: {' vs '.join([f'{ex}:{price:.6f}' for ex, price in exchanges.items()])}"
        )

    def transaction_sent(self, tx_hash: str, gas_price: int, gas_limit: int):
        """Log transaction submission."""
        self.logger.info(
            f"[SEND] TX_SENT: {tx_hash} | Gas: {gas_price} gwei | Limit: {gas_limit:,}"
        )

    def transaction_confirmed(self, tx_hash: str, profit_amount: float, gas_used: int):
        """Log successful transaction."""
        self.logger.info(
            f"[SUCCESS] TX_SUCCESS: {tx_hash} | Profit: {profit_amount:.6f} MATIC | Gas: {gas_used:,}"
        )

    def transaction_failed(self, tx_hash: str, error: str, gas_lost: int = 0):
        """Log failed transaction."""
        self.logger.error(
            f"[ERROR] TX_FAILED: {tx_hash} | Error: {error} | Gas Lost: {gas_lost:,}"
        )

    def risk_check_failed(self, reason: str, token_pair: str):
        """Log risk management rejection."""
        self.logger.warning(f"[WARNING] RISK_REJECTED: {token_pair} | Reason: {reason}")


def setup_logging(
        level: str = "INFO",
        log_to_file: bool = True,
        log_dir: str = "logs",
        use_colors: bool = True,
        use_rich: bool = False  # Disabled by default to avoid issues
) -> None:
    """
    Set up the logging system for the entire bot.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to files
        log_dir: Directory for log files
        use_colors: Whether to use colored output
        use_rich: Whether to use rich formatting (if available)
    """

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create logs directory
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Console handler setup
    if use_rich and RICH_AVAILABLE:
        # Use Rich handler for better formatting
        console = Console()
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True
        )
        console_handler.setLevel(numeric_level)
    else:
        # Use standard handler with custom formatter
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Set encoding for Windows compatibility
        if hasattr(console_handler.stream, 'reconfigure') and os.name == 'nt':
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except:
                pass
        
        console_handler.setLevel(numeric_level)
        console_formatter = ColoredFormatter(use_colors=use_colors)
        console_handler.setFormatter(console_formatter)

    root_logger.addHandler(console_handler)

    # File handler for general logs
    if log_to_file:
        file_handler = logging.FileHandler(
            Path(log_dir) / f"arbitrage_bot_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_formatter = ColoredFormatter(use_colors=False)  # No colors in files
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Separate file for trading events
        trading_handler = logging.FileHandler(
            Path(log_dir) / f"trading_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        trading_handler.setLevel(logging.INFO)
        trading_handler.addFilter(lambda record: 'TRADING' in record.name)
        trading_handler.setFormatter(file_formatter)
        root_logger.addHandler(trading_handler)

    # Set root logger level
    root_logger.setLevel(logging.DEBUG)

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("web3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Initial log message - Windows safe
    logger = get_logger("SETUP")
    logger.info("[ROCKET] Logging system initialized")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_trading_logger(name: str) -> TradingLogger:
    """
    Get a specialized trading logger.

    Args:
        name: Logger name

    Returns:
        TradingLogger instance
    """
    return TradingLogger(name)


# Performance logging utilities
class PerformanceLogger:
    """Logger for performance metrics and timing."""

    def __init__(self, name: str):
        self.logger = get_logger(f"PERF.{name}")
        self.start_times: Dict[str, float] = {}

    def start_timer(self, operation: str):
        """Start timing an operation."""
        import time
        self.start_times[operation] = time.time()

    def end_timer(self, operation: str, extra_info: str = ""):
        """End timing and log the duration."""
        import time
        if operation not in self.start_times:
            self.logger.warning(f"Timer '{operation}' was not started")
            return

        duration = time.time() - self.start_times[operation]
        del self.start_times[operation]

        info_str = f" | {extra_info}" if extra_info else ""
        self.logger.info(f"[TIMER] {operation}: {duration:.3f}s{info_str}")


def get_performance_logger(name: str) -> PerformanceLogger:
    """Get a performance logger instance."""
    return PerformanceLogger(name)


# Auto-setup logging when module is imported
if not logging.getLogger().handlers:
    setup_logging()