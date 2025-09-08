"""
Decimal handling utilities for proper token amount calculations
"""
# bot/decimal_utils.py

from web3 import Web3
import logging

logger = logging.getLogger(__name__)

# Standard token decimals
TOKEN_DECIMALS = {
    'USDC': 6,
    'USDT': 6,
    'DAI': 18,
    'WMATIC': 18,
    'WETH': 18,
    'WBTC': 8,
    'LINK': 18,
    'AAVE': 18,
    'CRV': 18,
    'SUSHI': 18,
    'QUICK': 18,
    'GHST': 18
}

# Reasonable price ranges for validation (approximate USD values)
PRICE_RANGES = {
    'USDC': (0.98, 1.02),  # Stablecoin
    'USDT': (0.98, 1.02),  # Stablecoin
    'DAI': (0.98, 1.02),  # Stablecoin
    'WMATIC': (0.3, 3.0),  # MATIC price range
    'WETH': (1500, 5000),  # ETH price range
    'WBTC': (25000, 100000),  # BTC price range
    'LINK': (5, 50),  # LINK price range
}


def get_token_decimals(token_address: str, token_map: dict) -> int:
    """Get decimals for a token address"""
    for symbol, address in token_map.items():
        if address.lower() == token_address.lower():
            return TOKEN_DECIMALS.get(symbol, 18)
    return 18  # Default to 18


def normalize_amount(amount: int, decimals: int) -> 'Decimal':
    """Convert wei amount to human-readable"""
    from decimal import Decimal
    if amount <= 0:
        return Decimal('0')
    return Decimal(amount) / Decimal(10 ** decimals)


def denormalize_amount(amount: float, decimals: int) -> int:
    """Convert human-readable amount to wei"""
    if amount <= 0:
        return 0
    return int(amount * (10 ** decimals))


def calculate_proper_price_ratio(amount_in: int, amount_out: int, decimals_in: int, decimals_out: int) -> float:
    """Calculate proper price ratio considering decimals"""
    if amount_in <= 0:
        return 0.0

    normalized_in = normalize_amount(amount_in, decimals_in)
    normalized_out = normalize_amount(amount_out, decimals_out)

    if normalized_in == 0:
        return 0.0

    ratio = normalized_out / normalized_in

    # Add debug logging for troubleshooting
    logger.debug(f"Price ratio calculation: {normalized_out:.8f} / {normalized_in:.8f} = {ratio:.8f}")

    return ratio


def validate_price_ratio(ratio: float, token_from: str, token_to: str, token_map: dict) -> bool:
    """Validate if a price ratio makes sense between two tokens"""
    if ratio <= 0:
        return False

    # Get token symbols
    from_symbol = get_token_name(token_from, token_map)
    to_symbol = get_token_name(token_to, token_map)

    # Special validation for stablecoin pairs
    stablecoins = {'USDC', 'USDT', 'DAI'}
    if from_symbol in stablecoins and to_symbol in stablecoins:
        # Stablecoin pairs should be very close to 1.0
        if not (0.95 <= ratio <= 1.05):
            logger.warning(f"Invalid stablecoin ratio: {from_symbol}->{to_symbol} = {ratio:.10f}")
            return False
        return True

    # For other pairs, check against reasonable bounds
    if ratio < 0.000001 or ratio > 1000000:
        logger.warning(f"Extreme price ratio: {from_symbol}->{to_symbol} = {ratio:.10f}")
        return False

    # Check against known price ranges if available
    if from_symbol in PRICE_RANGES and to_symbol in PRICE_RANGES:
        from_range = PRICE_RANGES[from_symbol]
        to_range = PRICE_RANGES[to_symbol]

        # Calculate expected ratio range
        min_expected = to_range[0] / from_range[1]  # min_to / max_from
        max_expected = to_range[1] / from_range[0]  # max_to / min_from

        if not (min_expected * 0.5 <= ratio <= max_expected * 2.0):  # Allow 50% buffer
            logger.warning(f"Price ratio outside expected range: {from_symbol}->{to_symbol} = {ratio:.6f}, "
                           f"expected: {min_expected:.6f} - {max_expected:.6f}")
            return False

    return True


def format_token_amount(amount: int, token_address: str, token_map: dict) -> str:
    """Format token amount with proper decimals"""
    decimals = get_token_decimals(token_address, token_map)
    normalized = normalize_amount(amount, decimals)
    return f"{normalized:.8f}"


def get_token_name(token_address: str, token_map: dict) -> str:
    """Get token name from address"""
    for name, addr in token_map.items():
        if addr.lower() == token_address.lower():
            return name
    return token_address[:8] + "..."  # Return truncated address if not found


def calculate_profit_percentage(buy_price: float, sell_price: float) -> float:
    """Calculate profit percentage between buy and sell prices"""
    if buy_price <= 0:
        return 0.0

    profit_pct = ((sell_price - buy_price) / buy_price) * 100

    # Sanity check: cap at reasonable maximum
    if profit_pct > 500:  # 500% max
        logger.warning(f"Unrealistic profit percentage calculated: {profit_pct:.2f}%")
        return 0.0

    return max(0.0, profit_pct)


def estimate_gas_cost_in_tokens(gas_units: int, gas_price_wei: int, token_price_usd: float,
                                matic_price_usd: float = 0.8) -> float:
    """Estimate gas cost in terms of tokens"""
    if gas_units <= 0 or gas_price_wei <= 0:
        return 0.0

    # Calculate gas cost in MATIC
    gas_cost_matic = (gas_units * gas_price_wei) / 10 ** 18

    # Convert to USD
    gas_cost_usd = gas_cost_matic * matic_price_usd

    # Convert to tokens
    if token_price_usd > 0:
        return gas_cost_usd / token_price_usd

    return 0.0
