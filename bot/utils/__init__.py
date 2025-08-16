# bot/utils/__init__.py
"""
Utility package for the flashloan arbitrage bot.

This package provides:
- Colored logging system (logger.py)
- Helper functions (helpers.py)
- Notification system (notifications.py)

Usage:
    from bot.utils.logger import get_logger
    from bot.utils.helpers import format_wei, calculate_gas_price
    from bot.utils.notifications import send_alert
"""

from .logger import get_logger, setup_logging
from .helpers import (
    format_wei,
    wei_to_ether,
    ether_to_wei,
    calculate_gas_price,
    validate_address,
    get_current_timestamp,
    calculate_percentage_difference,
    format_currency
)
from .notifications import (
    NotificationManager,
    send_discord_alert,
    send_telegram_alert,
    send_slack_alert
)

__version__ = "1.0.0"
__all__ = [
    # Logging
    "get_logger",
    "setup_logging",

    # Helpers
    "format_wei",
    "wei_to_ether",
    "ether_to_wei",
    "calculate_gas_price",
    "validate_address",
    "get_current_timestamp",
    "calculate_percentage_difference",
    "format_currency",

    # Notifications
    "NotificationManager",
    "send_discord_alert",
    "send_telegram_alert",
    "send_slack_alert"
]

# Default logger instance
logger = get_logger(__name__)
