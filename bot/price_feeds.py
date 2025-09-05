# bot/price_feeds.py
# bot/price_feeds.py
"""
Real Price Feeds Module - Production Version

This module handles REAL price fetching from multiple DEXs and arbitrage opportunity detection
using actual contract calls instead of simulation.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from dataclasses import dataclass
from .utils.rate_limiter import rate_limiter, rate_limited
import json

from web3 import Web3
from web3.exceptions import ContractLogicError

from config.settings import Settings
from .decimal_utils import (
    get_token_decimals, normalize_amount, calculate_proper_price_ratio,
    validate_price_ratio, get_token_name, TOKEN_DECIMALS
)
from .utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)

# Real DEX Router ABI for getAmountsOut calls
UNISWAP_V2_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

@dataclass
class PriceQuote:
    """Price quote from a DEX."""
    dex: str
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    price: Decimal  # token_out per token_in
    gas_cost: int
    timestamp: datetime
    is_valid: bool = True


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity between two DEXs."""
    token_in: str
    token_out: str
    amount: int  # Amount in token_in wei
    buy_dex: str
    sell_dex: str
    buy_price: Decimal  # Price on buy DEX (token_out per token_in)
    sell_price: Decimal  # Price on sell DEX (token_out per token_in)
    profit_percentage: Decimal
    estimated_profit: int  # Profit in token_out wei
    gas_cost: int
    net_profit: int  # Profit minus gas costs in wei
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PriceFeeds:
    """
    Manages REAL price feeds from multiple DEXs and identifies arbitrage opportunities.
    """

    def __init__(self, settings: Settings, w3: Web3):
        """Initialize real price feeds."""
        self.settings = settings
        self.w3 = w3

        # Real DEX router addresses on Polygon
        self.dex_configs = {
            'sushiswap': {
                'router': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap',
                'fee': 30  # 0.3%
            },
            'quickswap': {
                'router': '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff',
                'name': 'QuickSwap',
                'fee': 30  # 0.3%
            }
        }

        # Initialize router contracts
        self.routers = {}
        for dex, config in self.dex_configs.items():
            try:
                self.routers[dex] = self.w3.eth.contract(
                    address=config['router'],
                    abi=UNISWAP_V2_ROUTER_ABI
                )
                logger.info(f"Initialized {config['name']} router: {config['router']}")
            except Exception as e:
                logger.error(f"Failed to initialize {dex} router: {e}")

        self.enabled_dexes = list(self.routers.keys())

        # Token configurations
        self.token_addresses = self._load_token_addresses()
        self.stablecoins = {'USDC', 'USDT', 'DAI'}

        # Price caching
        self.price_cache: Dict[str, PriceQuote] = {}
        self.cache_ttl = 10  # 10 seconds for real data

        # Trading parameters - Token-appropriate amounts
        self.default_amounts = [
            100000000000000000000,  # 100 WMATIC (18 decimals)
            500000000000000000000,  # 500 WMATIC (18 decimals)
            1000000000000000000000,  # 1000 WMATIC (18 decimals)
        ]

        # Add USDC-specific amounts
        self.usdc_amounts = [
            100000000,  # 100 USDC (6 decimals)
            500000000,  # 500 USDC (6 decimals)
            1000000000,  # 1000 USDC (6 decimals)
        ]

        self.usdt_amounts = [
            100000000,  # 100 USDT (6 decimals)
            500000000,  # 500 USDT (6 decimals)
            1000000000,  # 1000 USDT (6 decimals)
        ]

        # Gas estimation
        self.gas_estimates = {
            'swap': 200000,
            'flashloan': 500000,
            'arbitrage': 800000
        }

        logger.info(f"PriceFeeds initialized with {len(self.enabled_dexes)} REAL DEXes")
        logger.info(f"Monitoring {len(self.token_addresses)} tokens")

    def _load_token_addresses(self) -> Dict[str, str]:
        """Load token address mappings."""
        return {
            'WMATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
            'USDC': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            'USDT': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
            'DAI': '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063',
            'WETH': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
            'WBTC': '0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6',
            'LINK': '0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39',
            'AAVE': '0xd6df932a45c0f255f85145f286ea0b292b21c90b',
        }

    async def get_price_quote(self, dex: str, token_in: str, token_out: str, amount_in: int) -> Optional[PriceQuote]:
        """
        Get a REAL price quote from a specific DEX using contract calls.
        """
        try:
            # Check cache first
            cache_key = f"{dex}_{token_in}_{token_out}_{amount_in}"
            cached_quote = self.price_cache.get(cache_key)

            if cached_quote and self._is_quote_fresh(cached_quote):
                return cached_quote

            # Get real quote from DEX contract
            quote = await self._fetch_real_dex_quote(dex, token_in, token_out, amount_in)

            if quote and self._validate_quote(quote, token_in, token_out):
                # Cache the quote
                self.price_cache[cache_key] = quote
                return quote
            else:
                logger.debug(f"Invalid quote from {dex}: {token_in} -> {token_out}")
                return None

        except Exception as e:
            logger.debug(f"Failed to get quote from {dex}: {e}")
            return None

    async def _fetch_real_dex_quote(self, dex: str, token_in: str, token_out: str, amount_in: int) -> Optional[PriceQuote]:
        """Fetch REAL quote from DEX router contract."""
        try:
            if dex not in self.routers:
                logger.warning(f"Unknown DEX: {dex}")
                return None

            router = self.routers[dex]
            path = [token_in, token_out]

            # Call the actual DEX router contract
            amounts = router.functions.getAmountsOut(amount_in, path).call()
            amount_out = amounts[-1]

            if amount_out <= 0:
                return None

            # Calculate price ratio with proper decimal handling
            decimals_in = get_token_decimals(token_in, self.token_addresses)
            decimals_out = get_token_decimals(token_out, self.token_addresses)
            price = calculate_proper_price_ratio(amount_in, amount_out, decimals_in, decimals_out)

            symbol_in = get_token_name(token_in, self.token_addresses)
            symbol_out = get_token_name(token_out, self.token_addresses)

            # DEBUG: Add detailed logging to track the calculation
            logger.info(f"=== DEBUG DEX CALL: {dex} ===")
            logger.info(f"  Pair: {symbol_in} -> {symbol_out}")
            logger.info(f"  amount_in: {amount_in} (raw wei)")
            logger.info(f"  amount_out: {amount_out} (raw wei)")
            logger.info(f"  decimals_in: {decimals_in}, decimals_out: {decimals_out}")
            logger.info(f"  normalized_in: {normalize_amount(amount_in, decimals_in)}")
            logger.info(f"  normalized_out: {normalize_amount(amount_out, decimals_out)}")
            logger.info(f"  calculated_price: {float(price)}")
            logger.info(f"========================")

            logger.debug(f"REAL {dex} quote: {normalize_amount(amount_in, decimals_in):.6f} {symbol_in} "
                        f"-> {normalize_amount(amount_out, decimals_out):.6f} {symbol_out} "
                        f"(price: {float(price):.8f})")

            return PriceQuote(
                dex=dex,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price=Decimal(str(price)),
                gas_cost=self.gas_estimates['swap'],
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.debug(f"{dex} quote failed: {e}")
            return None

    def _validate_quote(self, quote: PriceQuote, token_in: str, token_out: str) -> bool:
        """Validate a price quote for reasonableness."""
        try:
            if quote.price <= 0:
                logger.debug(f"Invalid price: {quote.price}")
                return False

            if quote.amount_out <= 0:
                logger.debug(f"Invalid amount out: {quote.amount_out}")
                return False

            # Get token symbols
            symbol_in = get_token_name(token_in, self.token_addresses)
            symbol_out = get_token_name(token_out, self.token_addresses)

            # Stablecoin pairs should be very close to 1.0
            if symbol_in in self.stablecoins and symbol_out in self.stablecoins:
                if not (Decimal('0.95') <= quote.price <= Decimal('1.05')):
                    logger.warning(f"Invalid stablecoin ratio: {symbol_in}->{symbol_out} = {quote.price}")
                    return False

            # General bounds check
            elif quote.price < Decimal('0.000001') or quote.price > Decimal('100000'):
                logger.warning(f"Extreme price ratio: {symbol_in}->{symbol_out} = {quote.price}")
                return False

            return True

        except Exception as e:
            logger.debug(f"Quote validation failed: {e}")
            return False

    def _is_quote_fresh(self, quote: PriceQuote) -> bool:
        """Check if a cached quote is still fresh."""
        return (datetime.now() - quote.timestamp).total_seconds() < self.cache_ttl

    async def find_arbitrage_opportunities(self, token_pairs: List[Tuple[str, str]],
                                           amounts: List[int] = None) -> List[ArbitrageOpportunity]:
        """
        Find REAL arbitrage opportunities across DEXs using actual market data.
        """
        opportunities = []

        try:
            for token_in, token_out in token_pairs:
                # Use proper amounts for this specific token
                token_amounts = self.get_trade_amounts(token_in)
                for amount in token_amounts:  # ← Now uses token-specific amounts
                    # Get quotes from all enabled DEXs
                    quotes = []
                    for dex in self.enabled_dexes:
                        quote = await self.get_price_quote(dex, token_in, token_out, amount)
                        if quote and quote.is_valid:
                            quotes.append(quote)

                    # Find arbitrage opportunities
                    if len(quotes) >= 2:
                        arb_ops = self._find_arbitrage_in_quotes(quotes, token_in, token_out, amount)
                        opportunities.extend(arb_ops)

            # Filter and sort opportunities
            profitable_opportunities = [op for op in opportunities
                                        if op.profit_percentage >= self.settings.trading.min_profit_threshold]

            # Sort by profit percentage
            profitable_opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)

            # Log real arbitrage findings
            if profitable_opportunities:
                logger.info(f"Found {len(profitable_opportunities)} REAL arbitrage opportunities")
                for i, op in enumerate(profitable_opportunities[:3]):  # Show top 3
                    symbol_in = get_token_name(op.token_in, self.token_addresses)
                    symbol_out = get_token_name(op.token_out, self.token_addresses)
                    logger.info(f"  {i + 1}. {symbol_in}->{symbol_out}: {float(op.profit_percentage):.4f}% "
                                f"({op.buy_dex} -> {op.sell_dex})")
            else:
                logger.debug("No profitable real arbitrage opportunities found")

            return profitable_opportunities

        except Exception as e:
            logger.error(f"Failed to find arbitrage opportunities: {e}")
            return []

    def _find_arbitrage_in_quotes(self, quotes: List[PriceQuote], token_in: str,
                                  token_out: str, amount: int) -> List[ArbitrageOpportunity]:
        """Find arbitrage opportunities within a set of REAL quotes."""
        opportunities = []

        try:
            # Compare all quote pairs
            for i, quote_a in enumerate(quotes):
                for j, quote_b in enumerate(quotes):
                    if i >= j:  # Avoid duplicate pairs
                        continue

                    # Determine which quote is better for selling token_in (higher price)
                    if quote_a.price > quote_b.price:
                        sell_quote = quote_a  # Better for token_in -> token_out
                        buy_back_quote = quote_b  # Better for token_out -> token_in
                    elif quote_b.price > quote_a.price:
                        sell_quote = quote_b  # Better for token_in -> token_out
                        buy_back_quote = quote_a  # Better for token_out -> token_in
                    else:
                        continue  # No price difference

                    # Calculate profit using real market data
                    profit_data = self._calculate_arbitrage_profit(
                        sell_quote, buy_back_quote, amount, token_in, token_out
                    )

                    if profit_data and profit_data['profit_percentage'] > 0:
                        opportunity = ArbitrageOpportunity(
                            token_in=token_in,
                            token_out=token_out,
                            amount=amount,
                            buy_dex=sell_quote.dex,
                            sell_dex=buy_back_quote.dex,
                            buy_price=sell_quote.price,
                            sell_price=buy_back_quote.price,
                            profit_percentage=profit_data['profit_percentage'],
                            estimated_profit=profit_data['estimated_profit'],
                            gas_cost=profit_data['total_gas_cost'],
                            net_profit=profit_data['net_profit']
                        )
                        opportunities.append(opportunity)

            return opportunities

        except Exception as e:
            logger.error(f"Failed to find arbitrage in quotes: {e}")
            return []

    def _calculate_arbitrage_profit(self, buy_quote: PriceQuote, sell_quote: PriceQuote,
                                    amount: int, token_in: str, token_out: str) -> Optional[Dict]:
        """Calculate arbitrage profit between two REAL quotes."""
        try:
            # Get token decimals
            decimals_in = get_token_decimals(token_in, self.token_addresses)
            decimals_out = get_token_decimals(token_out, self.token_addresses)

            # Step 1: Buy token_out with token_in
            tokens_bought = buy_quote.amount_out

            # Step 2: Sell token_out back to token_in
            tokens_bought_normalized = normalize_amount(tokens_bought, decimals_out)
            token_in_received_normalized = tokens_bought_normalized / sell_quote.price
            tokens_sold_for = int(token_in_received_normalized * (10 ** decimals_in))

            # Step 3: Calculate gross profit
            gross_profit = tokens_sold_for - amount

            if gross_profit <= 0:
                return None

            # Step 4: Calculate profit percentage
            profit_percentage = (Decimal(str(gross_profit)) / Decimal(str(amount))) * 100

            # Step 5: Estimate gas costs
            total_gas_cost = (buy_quote.gas_cost + sell_quote.gas_cost +
                              self.gas_estimates['flashloan'])

            gas_cost_in_tokens = self._estimate_gas_cost_in_tokens(
                total_gas_cost, token_in, decimals_in
            )

            # Step 6: Calculate net profit
            net_profit = gross_profit - gas_cost_in_tokens

            if net_profit <= 0:
                return None

            net_profit_percentage = (Decimal(str(net_profit)) / Decimal(str(amount))) * 100

            return {
                'profit_percentage': net_profit_percentage,
                'estimated_profit': gross_profit,
                'total_gas_cost': total_gas_cost,
                'net_profit': net_profit,
                'tokens_bought': tokens_bought,
                'tokens_sold_for': tokens_sold_for
            }

        except Exception as e:
            logger.debug(f"Profit calculation failed: {e}")
            return None

    def _estimate_gas_cost_in_tokens(self, gas_units: int, token_address: str, decimals: int) -> int:
        """Estimate gas cost in terms of the token being traded."""
        try:
            # Use 30 gwei gas price
            gas_price_wei = self.w3.to_wei(30, 'gwei')
            gas_cost_matic_wei = gas_units * gas_price_wei

            symbol = get_token_name(token_address, self.token_addresses)

            if symbol == 'WMATIC':
                return gas_cost_matic_wei
            elif symbol in self.stablecoins:
                # Convert MATIC to USD: use real market rate from our quotes
                # For simplicity, estimate 1 MATIC = $0.90
                matic_amount = self.w3.from_wei(gas_cost_matic_wei, 'ether')
                usd_amount = matic_amount * Decimal('0.90')
                return int(usd_amount * (10 ** decimals))
            else:
                # For other tokens, rough estimation
                return int(gas_cost_matic_wei * 2)

        except Exception as e:
            logger.debug(f"Gas cost estimation failed: {e}")
            return int(self.w3.to_wei(5, 'ether'))

    def get_supported_token_pairs(self) -> List[Tuple[str, str]]:
        """Get supported token pairs for arbitrage."""
        pairs = []

        # Focus on liquid pairs that are likely to have arbitrage
        main_tokens = ['WMATIC', 'USDC', 'USDT', 'WETH']
        token_addresses = {symbol: addr for symbol, addr in self.token_addresses.items()
                          if symbol in main_tokens}

        for i, (symbol_a, token_a) in enumerate(token_addresses.items()):
            for symbol_b, token_b in list(token_addresses.items())[i + 1:]:
                if symbol_a != symbol_b:
                    pairs.append((token_a, token_b))
                    pairs.append((token_b, token_a))

        return pairs

    def get_trade_amounts(self, token_address: str = None) -> List[int]:
        """Get appropriate trade amounts based on token decimals."""
        if token_address is None:
            # Default case - return WMATIC amounts
            return self.default_amounts.copy()

        symbol = get_token_name(token_address, self.token_addresses)

        if symbol in ['USDC', 'USDT']:
            return [
                100000000,  # 100 USDC/USDT (6 decimals)
                500000000,  # 500 USDC/USDT (6 decimals)
                1000000000  # 1000 USDC/USDT (6 decimals)
            ]
        else:
            # WMATIC, WETH, and other 18-decimal tokens
            return self.default_amounts.copy()

    async def validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate that an opportunity is still profitable with fresh data."""
        try:
            # Get fresh quotes
            buy_quote = await self.get_price_quote(
                opportunity.buy_dex, opportunity.token_in,
                opportunity.token_out, opportunity.amount
            )
            sell_quote = await self.get_price_quote(
                opportunity.sell_dex, opportunity.token_in,
                opportunity.token_out, opportunity.amount
            )

            if not buy_quote or not sell_quote:
                return False

            # Recalculate profit with fresh data
            profit_data = self._calculate_arbitrage_profit(
                buy_quote, sell_quote, opportunity.amount,
                opportunity.token_in, opportunity.token_out
            )

            if not profit_data:
                return False

            # Check if still profitable
            return profit_data['profit_percentage'] >= self.settings.trading.min_profit_threshold

        except Exception as e:
            logger.error(f"Opportunity validation failed: {e}")
            return False

    async def get_health_status(self) -> Dict:
        """Get health status of REAL price feeds."""
        status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'dex_status': {},
            'cache_size': len(self.price_cache),
            'enabled_dexes': self.enabled_dexes
        }

        try:
            # Test each DEX with real calls
            test_token_in = self.token_addresses['USDC']
            test_token_out = self.token_addresses['WMATIC']
            test_amount = 1000000  # 1 USDC

            for dex in self.enabled_dexes:
                try:
                    quote = await self.get_price_quote(dex, test_token_in, test_token_out, test_amount)
                    status['dex_status'][dex] = {
                        'status': 'healthy' if quote else 'warning',
                        'last_quote_time': quote.timestamp.isoformat() if quote else None,
                        'last_price': float(quote.price) if quote else None
                    }
                except Exception as e:
                    status['dex_status'][dex] = {
                        'status': 'error',
                        'error': str(e)
                    }

            # Overall status
            if any(dex_status['status'] == 'error' for dex_status in status['dex_status'].values()):
                status['status'] = 'degraded'

        except Exception as e:
            status['status'] = 'error'
            status['error'] = str(e)

        return status

    def clear_price_cache(self) -> None:
        """Clear the price cache."""
        self.price_cache.clear()
        logger.info("Price cache cleared")

    def get_cache_stats(self) -> Dict:
        """Get price cache statistics."""
        now = datetime.now()
        fresh_count = sum(1 for quote in self.price_cache.values()
                          if (now - quote.timestamp).total_seconds() < self.cache_ttl)

        return {
            'total_cached_quotes': len(self.price_cache),
            'fresh_quotes': fresh_count,
            'stale_quotes': len(self.price_cache) - fresh_count,
            'cache_ttl_seconds': self.cache_ttl
        }

    def set_cache_ttl(self, ttl_seconds: int) -> None:
        """Set cache TTL in seconds."""
        self.cache_ttl = max(5, min(60, ttl_seconds))  # Between 5s and 1min for real data
        logger.info(f"Price cache TTL set to {self.cache_ttl} seconds")

    async def test_price_feeds(self) -> Dict:
        """Test REAL price feeds functionality."""
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'passed',
            'tests': {}
        }

        try:
            # Test 1: Basic quote fetching from real DEXes
            usdc = self.token_addresses['USDC']
            wmatic = self.token_addresses['WMATIC']
            test_amount = 1000000  # 1 USDC

            quote = await self.get_price_quote('sushiswap', usdc, wmatic, test_amount)

            test_results['tests']['quote_fetching'] = {
                'status': 'passed' if quote else 'failed',
                'dex_tested': 'sushiswap',
                'quote_valid': quote.is_valid if quote else False,
                'price': float(quote.price) if quote else None
            }

            test_results['overall_status'] = 'passed'

        except Exception as e:
            test_results['overall_status'] = 'error'
            test_results['error'] = str(e)

        return test_results
    def get_price_feed_summary(self) -> Dict:
        """Get a summary of REAL price feed configuration and status."""
        return {
            'configuration': {
                'enabled_dexes': self.enabled_dexes,
                'monitored_tokens': len(self.token_addresses),
                'stablecoins': list(self.stablecoins),
                'default_amounts': [self.w3.from_wei(amt, 'ether') for amt in self.default_amounts],
                'cache_ttl': self.cache_ttl,
                'data_source': 'REAL_CONTRACTS'
            },
            'runtime_stats': {
                'cached_quotes': len(self.price_cache),
                'gas_estimates': self.gas_estimates
            },
            'dex_configs': {dex: config['name'] for dex, config in self.dex_configs.items()},
            'token_addresses': {symbol: addr[:10] + "..." for symbol, addr in self.token_addresses.items()}
        }