# bot/__init__.py
"""
Flashloan Arbitrage Bot Package

This package contains all the core components for the flashloan arbitrage bot:
- arbitrage_bot.py: Main orchestration and trading logic
- opportunity_scanner.py: Price difference detection across DEXs
- risk_manager.py: Safety checks and risk management
- contract_interface.py: Web3 contract interaction layer
- price_feeds.py: Price data aggregation from multiple sources
- utils/: Utility functions for logging, notifications, helpers

The bot uses Aave V3 flashloans to execute zero-capital arbitrage trades
on the Polygon network across multiple DEXs including 1inch, SushiSwap,
QuickSwap, and others.
"""

# Version information
__version__ = "1.0.0"
__author__ = "Flashloan Arbitrage Bot Team"

# Core components
from .arbitrage_bot import ArbitrageBot
from .opportunity_scanner import OpportunityScanner
from .risk_manager import RiskManager
from .contract_interface import ContractInterface
from .price_feeds import PriceFeeds

# Utilities
from .utils.logger import setup_logger
from .utils.notifications import NotificationManager
from .utils.helpers import (
    format_amount,
    calculate_profit_percentage,
    validate_address,
    get_token_decimals
)

# Package-level logger
import logging

logger = logging.getLogger(__name__)

# Available exports
__all__ = [
    # Core Classes
    "ArbitrageBot",
    "OpportunityScanner",
    "RiskManager",
    "ContractInterface",
    "PriceFeeds",

    # Utility Functions
    "setup_logger",
    "NotificationManager",
    "format_amount",
    "calculate_profit_percentage",
    "validate_address",
    "get_token_decimals",

    # Package Info
    "__version__",
    "__author__"
]


def get_version():
    """Get the current version of the bot package."""
    return __version__


def get_components():
    """Get a list of all available bot components."""
    return {
        "core": [
            "ArbitrageBot",
            "OpportunityScanner",
            "RiskManager",
            "ContractInterface",
            "PriceFeeds"
        ],
        "utilities": [
            "setup_logger",
            "NotificationManager",
            "format_amount",
            "calculate_profit_percentage",
            "validate_address",
            "get_token_decimals"
        ]
    }


# Package initialization message
logger.info(f"Flashloan Arbitrage Bot v{__version__} initialized")
logger.info("Core components: ArbitrageBot, OpportunityScanner, RiskManager, ContractInterface, PriceFeeds")
logger.info("Ready for Polygon network flashloan arbitrage trading")
