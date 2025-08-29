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
"""
Utility helper functions for the arbitrage bot
"""
import time
import json
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Union
from web3 import Web3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def format_amount(amount: Union[int, float, Decimal, str], decimals: int = 18, precision: int = 6) -> str:
    """
    Format token amount with proper decimal places
    
    Args:
        amount: Raw amount or wei amount
        decimals: Token decimals (default 18 for ETH/MATIC)
        precision: Display precision (default 6)
        
    Returns:
        Formatted amount string
    """
    try:
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        
        # Convert from wei if needed
        if decimals > 0:
            divisor = Decimal(10) ** decimals
            formatted = amount / divisor
        else:
            formatted = amount
        
        # Round to specified precision
        quantizer = Decimal(10) ** -precision
        rounded = formatted.quantize(quantizer, rounding=ROUND_HALF_UP)
        
        # Remove trailing zeros
        return str(rounded.normalize())
        
    except Exception as e:
        logger.error(f"Error formatting amount {amount}: {e}")
        return "0.000000"

def parse_amount(amount_str: str, decimals: int = 18) -> int:
    """
    Parse human-readable amount to wei
    
    Args:
        amount_str: Amount as string (e.g., "1.5")
        decimals: Token decimals (default 18)
        
    Returns:
        Amount in wei as integer
    """
    try:
        amount = Decimal(amount_str)
        multiplier = Decimal(10) ** decimals
        wei_amount = int(amount * multiplier)
        return wei_amount
    except Exception as e:
        logger.error(f"Error parsing amount {amount_str}: {e}")
        return 0

def calculate_slippage(expected_amount: Union[int, float], actual_amount: Union[int, float]) -> float:
    """
    Calculate slippage percentage between expected and actual amounts
    
    Args:
        expected_amount: Expected amount
        actual_amount: Actual received amount
        
    Returns:
        Slippage percentage (positive means loss, negative means gain)
    """
    try:
        if expected_amount == 0:
            return 0.0
            
        expected = float(expected_amount)
        actual = float(actual_amount)
        
        slippage = ((expected - actual) / expected) * 100
        return round(slippage, 4)
        
    except Exception as e:
        logger.error(f"Error calculating slippage: {e}")
        return 0.0

def calculate_gas_cost(gas_used: int, gas_price: int, native_token_price: float = None) -> Dict[str, float]:
    """
    Calculate gas cost in native token and USD
    
    Args:
        gas_used: Gas units used
        gas_price: Gas price in wei
        native_token_price: Price of native token in USD
        
    Returns:
        Dictionary with gas costs
    """
    try:
        # Calculate native token cost
        gas_cost_wei = gas_used * gas_price
        gas_cost_native = gas_cost_wei / (10**18)  # Convert wei to native token
        
        result = {
            'gas_used': gas_used,
            'gas_price_gwei': gas_price / (10**9),
            'cost_native': gas_cost_native,
            'cost_usd': 0.0
        }
        
        # Calculate USD cost if price provided
        if native_token_price:
            result['cost_usd'] = gas_cost_native * native_token_price
            
        return result
        
    except Exception as e:
        logger.error(f"Error calculating gas cost: {e}")
        return {'gas_used': 0, 'gas_price_gwei': 0, 'cost_native': 0, 'cost_usd': 0}

def estimate_profit(
    input_amount: int,
    buy_price: float,
    sell_price: float,
    gas_cost: float = 0,
    decimals: int = 18
) -> Dict[str, Any]:
    """
    Estimate arbitrage profit
    
    Args:
        input_amount: Input amount in wei
        buy_price: Buy price per token
        sell_price: Sell price per token  
        gas_cost: Gas cost in native token
        decimals: Token decimals
        
    Returns:
        Profit estimation dictionary
    """
    try:
        # Convert to human readable
        amount = input_amount / (10**decimals)
        
        # Calculate revenue and cost
        revenue = amount * sell_price
        cost = amount * buy_price
        gross_profit = revenue - cost
        net_profit = gross_profit - gas_cost
        
        # Calculate percentages
        profit_margin = (gross_profit / cost * 100) if cost > 0 else 0
        roi = (net_profit / cost * 100) if cost > 0 else 0
        
        return {
            'input_amount': amount,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'price_difference': sell_price - buy_price,
            'price_difference_pct': ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0,
            'gross_profit': gross_profit,
            'gas_cost': gas_cost,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'roi': roi,
            'profitable': net_profit > 0
        }
        
    except Exception as e:
        logger.error(f"Error estimating profit: {e}")
        return {'profitable': False, 'net_profit': 0}

def validate_address(address: str) -> bool:
    """
    Validate Ethereum address format
    
    Args:
        address: Address to validate
        
    Returns:
        True if valid address
    """
    try:
        return Web3.is_address(address)
    except:
        return False

def to_checksum_address(address: str) -> str:
    """
    Convert address to checksum format
    
    Args:
        address: Address to convert
        
    Returns:
        Checksum address
    """
    try:
        return Web3.to_checksum_address(address)
    except:
        return address

def create_trade_hash(
    token_in: str,
    token_out: str,
    amount_in: int,
    dex_in: str,
    dex_out: str,
    timestamp: int = None
) -> str:
    """
    Create unique hash for a trade
    
    Args:
        token_in: Input token address
        token_out: Output token address
        amount_in: Input amount
        dex_in: Input DEX name
        dex_out: Output DEX name
        timestamp: Trade timestamp
        
    Returns:
        Trade hash
    """
    if not timestamp:
        timestamp = int(time.time())
        
    trade_string = f"{token_in}{token_out}{amount_in}{dex_in}{dex_out}{timestamp}"
    return hashlib.md5(trade_string.encode()).hexdigest()

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry function on failure
    
    Args:
        max_retries: Maximum retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        
            raise last_exception
        return wrapper
    return decorator

def safe_divide(numerator: Union[int, float], denominator: Union[int, float]) -> float:
    """
    Safe division that returns 0 if denominator is 0
    """
    try:
        if denominator == 0:
            return 0.0
        return float(numerator) / float(denominator)
    except:
        return 0.0

def get_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def truncate_address(address: str, start_chars: int = 6, end_chars: int = 4) -> str:
    """
    Truncate address for display (0x1234...5678)
    """
    if len(address) <= start_chars + end_chars:
        return address
    return f"{address[:start_chars]}...{address[-end_chars:]}"

def format_duration(seconds: float) -> str:
    """
    Format duration in human readable format
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def validate_private_key(private_key: str) -> bool:
    """
    Validate private key format
    """
    try:
        if not private_key:
            return False
        
        # Remove 0x prefix if present
        if private_key.startswith('0x'):
            private_key = private_key[2:]
            
        # Check if it's 64 hex characters
        if len(private_key) != 64:
            return False
            
        # Try to convert to int to validate hex
        int(private_key, 16)
        return True
        
    except:
        return False

def load_json_file(file_path: str) -> Dict[str, Any]:
    """
    Safely load JSON file
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return {}

def save_json_file(data: Dict[str, Any], file_path: str) -> bool:
    """
    Safely save JSON file
    """
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {e}")
        return False

def is_profitable_after_gas(profit_usd: float, gas_cost_usd: float, min_profit_usd: float = 1.0) -> bool:
    """
    Check if trade is profitable after gas costs
    """
    net_profit = profit_usd - gas_cost_usd
    return net_profit >= min_profit_usd

def get_current_timestamp() -> int:
    """Get current timestamp in seconds"""
    return int(time.time())

def timestamp_to_datetime(timestamp: int) -> datetime:
    """Convert timestamp to datetime"""
    return datetime.fromtimestamp(timestamp)

def datetime_to_timestamp(dt: datetime) -> int:
    """Convert datetime to timestamp"""
    return int(dt.timestamp())

# Rate limiting helper
class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def is_allowed(self) -> bool:
        """Check if call is allowed"""
        now = time.time()
        
        # Remove old calls
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        # Check if we can make another call
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False
    
    def wait_time(self) -> float:
        """Get time to wait before next call"""
        if not self.calls:
            return 0
        
        oldest_call = min(self.calls)
        wait_time = self.time_window - (time.time() - oldest_call)
        return max(0, wait_time)
def calculate_profit_percentage(buy_price: float, sell_price: float, gas_cost: float = 0.0) -> float:
    """
    Calculate profit percentage after accounting for gas costs
    
    Args:
        buy_price: Price when buying
        sell_price: Price when selling  
        gas_cost: Gas cost in the same currency
    
    Returns:
        Profit percentage (can be negative)
    """
    if buy_price <= 0:
        return 0.0
    
    revenue = sell_price - buy_price - gas_cost
    return (revenue / buy_price) * 100.0

def get_token_decimals(token_address: str, default: int = 18) -> int:
    """
    Get token decimals for a given token address.
    
    Args:
        token_address: Token contract address
        default: Default decimals if not found
    
    Returns:
        Number of decimals for the token
    """
    # Common token decimals (you can expand this list)
    common_tokens = {
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174": 6,  # USDC
        "0xc2132D05D31c914a87C6611C10748AEb04B58e8F": 6,  # USDT
        "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063": 18, # DAI
        "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270": 18, # WMATIC
        "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619": 18, # WETH
        "0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6": 8,  # WBTC
    }
    
    return common_tokens.get(token_address.lower(), default)
