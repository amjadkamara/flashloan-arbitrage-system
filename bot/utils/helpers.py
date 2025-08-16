# bot/utils/helpers.py
"""
Helper functions for the flashloan arbitrage bot.

Provides utility functions for:
- Wei/Ether conversions
- Gas price calculations
- Address validation
- Percentage calculations
- Currency formatting
- Time utilities

Usage:
    from bot.utils.helpers import format_wei, calculate_gas_price

    formatted = format_wei(1000000000000000000)  # "1.0 MATIC"
    gas_price = calculate_gas_price(speed="fast")
"""

import time
import re
from decimal import Decimal, getcontext
from typing import Union, Optional, Dict, Any, List
from datetime import datetime, timezone
import requests
from web3 import Web3

# Set high precision for decimal calculations
getcontext().prec = 50

# Constants
WEI_PER_ETHER = 10 ** 18
GWEI_PER_ETH = 10 ** 9
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


def format_wei(wei_amount: Union[int, str], decimals: int = 18, symbol: str = "MATIC") -> str:
    """
    Format wei amount to human-readable string.

    Args:
        wei_amount: Amount in wei
        decimals: Token decimals (default 18)
        symbol: Token symbol for display

    Returns:
        Formatted string like "1.234 MATIC"
    """
    if not wei_amount:
        return f"0.0 {symbol}"

    try:
        amount = Decimal(str(wei_amount)) / Decimal(10 ** decimals)

        # Format with appropriate precision
        if amount >= 1000:
            formatted = f"{amount:,.2f}"
        elif amount >= 1:
            formatted = f"{amount:.4f}"
        elif amount >= 0.01:
            formatted = f"{amount:.6f}"
        else:
            formatted = f"{amount:.8f}"

        return f"{formatted} {symbol}"
    except (ValueError, TypeError):
        return f"Invalid {symbol}"


def wei_to_ether(wei_amount: Union[int, str], decimals: int = 18) -> Decimal:
    """
    Convert wei to ether with high precision.

    Args:
        wei_amount: Amount in wei
        decimals: Token decimals

    Returns:
        Decimal amount in ether
    """
    try:
        return Decimal(str(wei_amount)) / Decimal(10 ** decimals)
    except (ValueError, TypeError):
        return Decimal('0')


def ether_to_wei(ether_amount: Union[float, str, Decimal], decimals: int = 18) -> int:
    """
    Convert ether to wei.

    Args:
        ether_amount: Amount in ether
        decimals: Token decimals

    Returns:
        Amount in wei as integer
    """
    try:
        decimal_amount = Decimal(str(ether_amount))
        wei_amount = decimal_amount * Decimal(10 ** decimals)
        return int(wei_amount)
    except (ValueError, TypeError):
        return 0


def calculate_gas_price(
        speed: str = "standard",
        polygon_gas_station_url: str = "https://gasstation.polygon.technology/v2"
) -> Optional[int]:
    """
    Calculate gas price for Polygon network.

    Args:
        speed: Gas speed ("safeLow", "standard", "fast", "fastest")
        polygon_gas_station_url: URL for Polygon gas station API

    Returns:
        Gas price in gwei, or None if failed
    """
    try:
        response = requests.get(polygon_gas_station_url, timeout=5)
        response.raise_for_status()
        gas_data = response.json()

        # Map speed to API response
        speed_map = {
            "safeLow": "safeLow",
            "safe_low": "safeLow",
            "standard": "standard",
            "fast": "fast",
            "fastest": "fastest"
        }

        api_speed = speed_map.get(speed, "standard")

        if api_speed in gas_data:
            # Gas prices are returned in gwei, convert to wei for web3
            gas_price_gwei = gas_data[api_speed]["maxFee"]
            return int(gas_price_gwei * GWEI_PER_ETH)

        # Fallback to standard if specific speed not available
        if "standard" in gas_data:
            gas_price_gwei = gas_data["standard"]["maxFee"]
            return int(gas_price_gwei * GWEI_PER_ETH)

        return None

    except Exception:
        # Fallback gas prices in gwei (converted to wei)
        fallback_prices = {
            "safeLow": 30 * GWEI_PER_ETH,
            "safe_low": 30 * GWEI_PER_ETH,
            "standard": 40 * GWEI_PER_ETH,
            "fast": 60 * GWEI_PER_ETH,
            "fastest": 80 * GWEI_PER_ETH
        }
        return fallback_prices.get(speed, 40 * GWEI_PER_ETH)


def validate_address(address: str) -> bool:
    """
    Validate Ethereum/Polygon address format.

    Args:
        address: Address to validate

    Returns:
        True if valid address format
    """
    if not address:
        return False

    # Check if it's a valid hex string with correct length
    if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
        return False

    # Additional validation using Web3
    try:
        return Web3.is_address(address)
    except Exception:
        return False


def get_current_timestamp() -> int:
    """
    Get current Unix timestamp.

    Returns:
        Current timestamp as integer
    """
    return int(time.time())


def get_current_datetime() -> str:
    """
    Get current datetime in ISO format.

    Returns:
        Current datetime string
    """
    return datetime.now(timezone.utc).isoformat()


def calculate_percentage_difference(price1: float, price2: float) -> float:
    """
    Calculate percentage difference between two prices.

    Args:
        price1: First price (typically lower)
        price2: Second price (typically higher)

    Returns:
        Percentage difference (positive if price2 > price1)
    """
    if not price1 or not price2:
        return 0.0

    try:
        return ((price2 - price1) / price1) * 100
    except (ZeroDivisionError, TypeError):
        return 0.0


def calculate_arbitrage_profit(
        amount_in: Union[int, str],
        price_buy: float,
        price_sell: float,
        gas_cost: Union[int, str] = 0,
        decimals: int = 18
) -> Dict[str, Any]:
    """
    Calculate arbitrage profit potential.

    Args:
        amount_in: Input amount in wei
        price_buy: Buy price per token
        price_sell: Sell price per token
        gas_cost: Estimated gas cost in wei
        decimals: Token decimals

    Returns:
        Dictionary with profit calculations
    """
    try:
        # Convert to decimal for precision
        amount_decimal = wei_to_ether(amount_in, decimals)
        gas_cost_decimal = wei_to_ether(gas_cost, 18)  # Gas always in MATIC

        # Calculate amounts
        tokens_bought = amount_decimal / Decimal(str(price_buy))
        revenue = tokens_bought * Decimal(str(price_sell))
        gross_profit = revenue - amount_decimal
        net_profit = gross_profit - gas_cost_decimal

        # Calculate percentages
        profit_percentage = float((net_profit / amount_decimal) * 100) if amount_decimal > 0 else 0
        price_difference = calculate_percentage_difference(price_buy, price_sell)

        return {
            "amount_in": float(amount_decimal),
            "tokens_bought": float(tokens_bought),
            "revenue": float(revenue),
            "gross_profit": float(gross_profit),
            "gas_cost": float(gas_cost_decimal),
            "net_profit": float(net_profit),
            "profit_percentage": profit_percentage,
            "price_difference": price_difference,
            "is_profitable": net_profit > 0
        }

    except Exception:
        return {
            "amount_in": 0,
            "tokens_bought": 0,
            "revenue": 0,
            "gross_profit": 0,
            "gas_cost": 0,
            "net_profit": 0,
            "profit_percentage": 0,
            "price_difference": 0,
            "is_profitable": False
        }


def format_currency(
        amount: Union[float, Decimal, int],
        currency: str = "USD",
        decimals: int = 2
) -> str:
    """
    Format amount as currency string.

    Args:
        amount: Amount to format
        currency: Currency symbol
        decimals: Decimal places

    Returns:
        Formatted currency string
    """
    try:
        if currency == "USD":
            return f"${float(amount):,.{decimals}f}"
        elif currency == "MATIC":
            return f"{float(amount):,.{decimals}f} MATIC"
        else:
            return f"{float(amount):,.{decimals}f} {currency}"
    except (ValueError, TypeError):
        return f"0.00 {currency}"


def format_percentage(percentage: float, decimals: int = 2, show_sign: bool = True) -> str:
    """
    Format percentage with appropriate sign and decimals.

    Args:
        percentage: Percentage value
        decimals: Decimal places
        show_sign: Whether to show + for positive values

    Returns:
        Formatted percentage string
    """
    try:
        if show_sign and percentage > 0:
            return f"+{percentage:.{decimals}f}%"
        else:
            return f"{percentage:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def chunks(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks of specified size.

    Args:
        lst: List to split
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def retry_with_backoff(
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0
):
    """
    Retry function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay

    Returns:
        Function result or raises last exception
    """

    def wrapper(*args, **kwargs):
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= backoff_factor

        raise last_exception

    return wrapper


def is_contract_address(web3_instance, address: str) -> bool:
    """
    Check if address is a contract (has code).

    Args:
        web3_instance: Web3 instance
        address: Address to check

    Returns:
        True if address is a contract
    """
    try:
        if not validate_address(address):
            return False

        code = web3_instance.eth.get_code(Web3.to_checksum_address(address))
        return len(code) > 0
    except Exception:
        return False


def calculate_slippage_amount(
        amount: Union[int, str],
        slippage_percent: float,
        is_minimum: bool = True
) -> int:
    """
    Calculate amount with slippage protection.

    Args:
        amount: Original amount
        slippage_percent: Slippage percentage (e.g., 0.5 for 0.5%)
        is_minimum: True for minimum out, False for maximum in

    Returns:
        Amount adjusted for slippage
    """
    try:
        amount_decimal = Decimal(str(amount))
        slippage_factor = Decimal(str(slippage_percent)) / Decimal('100')

        if is_minimum:
            # Minimum amount out (reduce by slippage)
            adjusted = amount_decimal * (Decimal('1') - slippage_factor)
        else:
            # Maximum amount in (increase by slippage)
            adjusted = amount_decimal * (Decimal('1') + slippage_factor)

        return int(adjusted)
    except Exception:
        return int(amount) if isinstance(amount, str) else amount


# Time-related helpers
def seconds_until_next_minute() -> int:
    """Get seconds until next minute."""
    now = datetime.now()
    return SECONDS_PER_MINUTE - now.second


def seconds_until_next_hour() -> int:
    """Get seconds until next hour."""
    now = datetime.now()
    return SECONDS_PER_HOUR - (now.minute * SECONDS_PER_MINUTE + now.second)


def format_duration(seconds: Union[int, float]) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    try:
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f}h"
        else:
            days = seconds / 86400
            return f"{days:.1f}d"
    except (ValueError, TypeError):
        return "0s"
# Helper functions
