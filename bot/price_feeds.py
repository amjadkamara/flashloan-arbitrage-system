# bot/price_feeds.py
"""
Price Feeds Module - Fixed Version

This module handles price fetching from multiple DEXs and arbitrage opportunity detection
with proper decimal handling, price validation, and profit calculations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from dataclasses import dataclass
from .utils.rate_limiter import rate_limiter, rate_limited
import json
import aiohttp
from collections import defaultdict

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
    Manages price feeds from multiple DEXs and identifies arbitrage opportunities.
    """

    def __init__(self, settings: Settings, w3: Web3):
        """Initialize price feeds."""
        self.settings = settings
        self.w3 = w3

        # DEX configurations
        self.dex_configs = self._load_dex_configs()
        self.enabled_dexes = self.settings.dex.enabled_dexes

        # Token configurations
        self.token_addresses = self._load_token_addresses()
        self.stablecoins = {'USDC', 'USDT', 'DAI'}

        # Price caching
        self.price_cache: Dict[str, PriceQuote] = {}
        self.cache_ttl = 30  # 30 seconds

        # Trading parameters
        self.default_amounts = [
            self.w3.to_wei(100, 'ether'),  # 100 MATIC
            self.w3.to_wei(500, 'ether'),  # 500 MATIC
            self.w3.to_wei(1000, 'ether'),  # 1000 MATIC
            self.w3.to_wei(2500, 'ether'),  # 2500 MATIC
        ]

        # Gas estimation
        self.gas_estimates = {
            'swap': 200000,
            'flashloan': 500000,
            'arbitrage': 800000
        }

        logger.info(f"PriceFeeds initialized with {len(self.enabled_dexes)} DEXs")
        logger.info(f"Monitoring {len(self.token_addresses)} tokens")

    def _load_dex_configs(self) -> Dict:
        """Load DEX router configurations."""
        return {
            'uniswap_v3': {
                'router': self.settings.dex.uniswap_v3_router,
                'name': 'Uniswap V3',
                'fee_tier': self.settings.dex.default_fee_tier
            },
            'sushiswap': {
                'router': self.settings.dex.sushiswap_router,
                'name': 'SushiSwap',
                'fee': 30  # 0.3%
            },
            'quickswap': {
                'router': self.settings.dex.quickswap_router,
                'name': 'QuickSwap',
                'fee': 30  # 0.3%
            },
            'balancer': {
                'vault': self.settings.dex.balancer_vault,
                'name': 'Balancer',
                'fee': 50  # 0.5% average
            }
        }

    def _load_token_addresses(self) -> Dict[str, str]:
        """Load token address mappings."""
        # These should come from your token configuration
        # Using common Polygon token addresses as examples
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
        Get a price quote from a specific DEX.

        Args:
            dex: DEX identifier
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount in wei

        Returns:
            PriceQuote or None if failed
        """
        try:
            # Check cache first
            cache_key = f"{dex}_{token_in}_{token_out}_{amount_in}"
            cached_quote = self.price_cache.get(cache_key)

            if cached_quote and self._is_quote_fresh(cached_quote):
                return cached_quote

            # Get quote from DEX
            quote = await self._fetch_dex_quote(dex, token_in, token_out, amount_in)

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

    async def _fetch_dex_quote(self, dex: str, token_in: str, token_out: str, amount_in: int) -> Optional[PriceQuote]:
        """Fetch quote from specific DEX implementation."""
        try:
            if dex == 'uniswap_v3':
                return await self._get_uniswap_v3_quote(token_in, token_out, amount_in)
            elif dex in ['sushiswap', 'quickswap']:
                return await self._get_uniswap_v2_quote(dex, token_in, token_out, amount_in)
            elif dex == 'balancer':
                return await self._get_balancer_quote(token_in, token_out, amount_in)
            else:
                logger.warning(f"Unknown DEX: {dex}")
                return None

        except Exception as e:
            logger.debug(f"DEX quote fetch failed for {dex}: {e}")
            return None

    async def _get_uniswap_v3_quote(self, token_in: str, token_out: str, amount_in: int) -> Optional[PriceQuote]:
        """Get quote from Uniswap V3."""
        try:
            # This would typically call the Uniswap V3 quoter contract
            # For now, using a simplified simulation

            # Get token decimals
            decimals_in = get_token_decimals(token_in, self.token_addresses)
            decimals_out = get_token_decimals(token_out, self.token_addresses)

            # Simulate price calculation (replace with actual quoter call)
            amount_out = await self._simulate_swap_amount_out(
                'uniswap_v3', token_in, token_out, amount_in, decimals_in, decimals_out
            )

            if amount_out <= 0:
                return None

            # Calculate price ratio with proper decimal handling
            price = calculate_proper_price_ratio(amount_in, amount_out, decimals_in, decimals_out)

            return PriceQuote(
                dex='uniswap_v3',
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price=Decimal(str(price)),
                gas_cost=self.gas_estimates['swap'],
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.debug(f"Uniswap V3 quote failed: {e}")
            return None

    async def _get_uniswap_v2_quote(self, dex: str, token_in: str, token_out: str, amount_in: int) -> Optional[
        PriceQuote]:
        """Get quote from Uniswap V2 style DEX (SushiSwap, QuickSwap)."""
        try:
            # Get token decimals
            decimals_in = get_token_decimals(token_in, self.token_addresses)
            decimals_out = get_token_decimals(token_out, self.token_addresses)

            # Simulate swap (replace with actual router call)
            amount_out = await self._simulate_swap_amount_out(
                dex, token_in, token_out, amount_in, decimals_in, decimals_out
            )

            if amount_out <= 0:
                return None

            # Calculate price ratio with proper decimal handling
            price = calculate_proper_price_ratio(amount_in, amount_out, decimals_in, decimals_out)

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

    async def _get_balancer_quote(self, token_in: str, token_out: str, amount_in: int) -> Optional[PriceQuote]:
        """Get quote from Balancer."""
        try:
            # Get token decimals
            decimals_in = get_token_decimals(token_in, self.token_addresses)
            decimals_out = get_token_decimals(token_out, self.token_addresses)

            # Simulate swap (replace with actual Balancer vault call)
            amount_out = await self._simulate_swap_amount_out(
                'balancer', token_in, token_out, amount_in, decimals_in, decimals_out
            )

            if amount_out <= 0:
                return None

            # Calculate price ratio with proper decimal handling
            price = calculate_proper_price_ratio(amount_in, amount_out, decimals_in, decimals_out)

            return PriceQuote(
                dex='balancer',
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price=Decimal(str(price)),
                gas_cost=self.gas_estimates['swap'],
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.debug(f"Balancer quote failed: {e}")
            return None

    async def _simulate_swap_amount_out(self, dex: str, token_in: str, token_out: str,
                                        amount_in: int, decimals_in: int, decimals_out: int) -> int:
        """
        Simulate swap amount out calculation.

        THIS IS A PLACEHOLDER - Replace with actual DEX contract calls.
        """
        try:
            # Get token symbols for simulation
            symbol_in = get_token_name(token_in, self.token_addresses)
            symbol_out = get_token_name(token_out, self.token_addresses)

            # Normalize input amount
            amount_in_normalized = normalize_amount(amount_in, decimals_in)

            # Simulate realistic prices based on token types
            if symbol_in in self.stablecoins and symbol_out in self.stablecoins:
                # Stablecoin to stablecoin - should be close to 1:1
                simulated_price = Decimal('0.999')  # Slight discount for fees
                amount_out_normalized = amount_in_normalized * simulated_price

            elif symbol_in == 'WMATIC' and symbol_out in self.stablecoins:
                # MATIC to stablecoin - simulate MATIC at ~$0.80
                simulated_price = Decimal('0.80')
                amount_out_normalized = amount_in_normalized * simulated_price

            elif symbol_in in self.stablecoins and symbol_out == 'WMATIC':
                # Stablecoin to MATIC - add DEX-specific variations
                base_price = Decimal('1.25')  # 1 USD = 1.25 MATIC (inverse of 0.80)
                
                # Add DEX-specific price variations to create arbitrage opportunities
                if dex == 'uniswap_v3':
                    simulated_price = base_price * Decimal('1.02')  # 2% higher
                elif dex == 'sushiswap':
                    simulated_price = base_price * Decimal('0.98')  # 2% lower  
                elif dex == 'quickswap':
                    simulated_price = base_price * Decimal('1.01')  # 1% higher
                elif dex == 'balancer':
                    simulated_price = base_price * Decimal('0.99')  # 1% lower
                else:
                    simulated_price = base_price  # 1 USD = 1.25 MATIC (inverse of 0.80)
                amount_out_normalized = amount_in_normalized * simulated_price

            elif symbol_in == 'WMATIC' and symbol_out == 'WETH':
                # MATIC to ETH - simulate ETH at ~$2500, MATIC at ~$0.80
                simulated_price = Decimal('0.00032')  # 0.80 / 2500
                amount_out_normalized = amount_in_normalized * simulated_price

            elif symbol_in == 'WETH' and symbol_out == 'WMATIC':
                # ETH to MATIC
                simulated_price = Decimal('3125')  # 2500 / 0.80
                amount_out_normalized = amount_in_normalized * simulated_price

            else:
                # Default case - simulate 1:1 ratio for unknown pairs
                logger.debug(f"Unknown token pair simulation: {symbol_in} -> {symbol_out}")
                amount_out_normalized = amount_in_normalized * Decimal('0.95')  # 5% slippage

            # Apply DEX-specific fee
            fee_multiplier = Decimal('0.997')  # 0.3% fee
            if dex == 'balancer':
                fee_multiplier = Decimal('0.995')  # 0.5% fee

            amount_out_normalized *= fee_multiplier

            # Convert back to wei
            amount_out = int(amount_out_normalized * (10 ** decimals_out))

            logger.debug(f"Simulated swap: {amount_in_normalized:.6f} {symbol_in} -> "
                         f"{amount_out_normalized:.6f} {symbol_out} on {dex}")

            return max(0, amount_out)

        except Exception as e:
            logger.debug(f"Swap simulation failed: {e}")
            return 0

    def _validate_quote(self, quote: PriceQuote, token_in: str, token_out: str) -> bool:
        """
        Validate a price quote for reasonableness.

        FIXED: Proper validation logic with stablecoin checks
        """
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

            # FIXED: Strict stablecoin validation
            if symbol_in in self.stablecoins and symbol_out in self.stablecoins:
                # Stablecoin pairs should be very close to 1.0
                if not (Decimal('0.95') <= quote.price <= Decimal('1.05')):
                    logger.warning(f"Invalid stablecoin ratio: {symbol_in}->{symbol_out} = {quote.price}")
                    return False

            # FIXED: More reasonable general bounds
            elif quote.price < Decimal('0.000001') or quote.price > Decimal('100000'):
                logger.warning(f"Extreme price ratio: {symbol_in}->{symbol_out} = {quote.price}")
                return False

            # Use decimal_utils validation for additional checks
            price_float = float(quote.price)
            if not validate_price_ratio(price_float, token_in, token_out, self.token_addresses):
                return False

            return True

        except Exception as e:
            logger.debug(f"Quote validation failed: {e}")
            return False

    def _is_quote_fresh(self, quote: PriceQuote) -> bool:
        """Check if a cached quote is still fresh."""
        return (datetime.now() - quote.timestamp).total_seconds() < self.cache_ttl

    async def find_arbitrage_opportunities(self, token_pairs: List[Tuple[str, str]],
                                           amounts: List[int]) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities across DEXs.

        FIXED: Proper profit calculation logic
        """
        opportunities = []

        try:
            for token_in, token_out in token_pairs:
                for amount in amounts:
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

            return profitable_opportunities

        except Exception as e:
            logger.error(f"Failed to find arbitrage opportunities: {e}")
            return []

    def _find_arbitrage_in_quotes(self, quotes: List[PriceQuote], token_in: str,
                                  token_out: str, amount: int) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities within a set of quotes.

        CORRECTED: Fixed quote assignment for proper arbitrage direction

        For flashloan arbitrage with token_in -> token_out -> token_in:
        1. We borrow token_in via flashloan
        2. We sell token_in for token_out where we get the MOST token_out (highest price)
        3. We buy token_in with token_out where we pay the LEAST token_out (lowest reverse price)
        4. We repay the flashloan and keep the profit
        """
        opportunities = []

        try:
            # Compare all quote pairs
            for i, quote_a in enumerate(quotes):
                for j, quote_b in enumerate(quotes):
                    if i >= j:  # Avoid duplicate pairs
                        continue

                    # Determine which quote is better for selling token_in (higher price)
                    # and which is better for buying token_in back (lower reverse price)
                    if quote_a.price > quote_b.price:
                        # quote_a gives more token_out per token_in (better for selling token_in)
                        # quote_b gives less token_out per token_in (better for buying token_in back)
                        sell_quote = quote_a  # Use for token_in -> token_out
                        buy_back_quote = quote_b  # Use for token_out -> token_in
                    elif quote_b.price > quote_a.price:
                        # quote_b gives more token_out per token_in (better for selling token_in)
                        # quote_a gives less token_out per token_in (better for buying token_in back)
                        sell_quote = quote_b  # Use for token_in -> token_out
                        buy_back_quote = quote_a  # Use for token_out -> token_in
                    else:
                        continue  # No price difference, no arbitrage opportunity

                    # Calculate profit using corrected quote assignment
                    profit_data = self._calculate_arbitrage_profit(
                        sell_quote, buy_back_quote, amount, token_in, token_out
                    )

                    if profit_data and profit_data['profit_percentage'] > 0:
                        opportunity = ArbitrageOpportunity(
                            token_in=token_in,
                            token_out=token_out,
                            amount=amount,
                            buy_dex=sell_quote.dex,  # DEX where we sell token_in (first step)
                            sell_dex=buy_back_quote.dex,  # DEX where we buy token_in back (second step)
                            buy_price=sell_quote.price,  # Price for token_in -> token_out
                            sell_price=buy_back_quote.price,  # Price for token_out -> token_in conversion
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
        """
        Calculate arbitrage profit between two quotes.

        CORRECTED: Fixed profit calculation logic for flashloan arbitrage

        Flashloan arbitrage flow:
        1. Borrow token_in via flashloan
        2. Buy token_out on cheaper DEX using token_in
        3. Sell token_out back to token_in on more expensive DEX
        4. Repay flashloan + keep profit
        """
        try:
            # Get token decimals
            decimals_in = get_token_decimals(token_in, self.token_addresses)
            decimals_out = get_token_decimals(token_out, self.token_addresses)

            # Step 1: Buy token_out on cheaper DEX
            # Amount of token_out we get from buy_quote
            tokens_bought = buy_quote.amount_out  # Already in token_out wei

            # Step 2: Sell token_out on more expensive DEX
            # Calculate how much token_in we get when selling tokens_bought
            # sell_quote.price = token_out per token_in
            # To get token_in from token_out: divide by price

            # Convert tokens_bought to normalized amount
            tokens_bought_normalized = normalize_amount(tokens_bought, decimals_out)

            # Calculate token_in received (normalized)
            token_in_received_normalized = tokens_bought_normalized / sell_quote.price

            # Convert back to wei
            tokens_sold_for = int(token_in_received_normalized * (10 ** decimals_in))

            # Step 3: Calculate gross profit
            gross_profit = tokens_sold_for - amount  # Profit in token_in wei

            if gross_profit <= 0:
                return None

            # Step 4: Calculate profit percentage
            profit_percentage = (Decimal(str(gross_profit)) / Decimal(str(amount))) * 100

            # Step 5: Estimate gas costs
            total_gas_cost = (buy_quote.gas_cost + sell_quote.gas_cost +
                              self.gas_estimates['flashloan'])

            # Convert gas cost to token_in equivalent
            gas_cost_in_tokens = self._estimate_gas_cost_in_tokens(
                total_gas_cost, token_in, decimals_in
            )

            # Step 6: Calculate net profit
            net_profit = gross_profit - gas_cost_in_tokens

            # Final validation
            if net_profit <= 0:
                return None

            net_profit_percentage = (Decimal(str(net_profit)) / Decimal(str(amount))) * 100

            # Debug logging for verification
            logger.debug(f"Arbitrage calculation for {get_token_name(token_in, self.token_addresses)}->"
                         f"{get_token_name(token_out, self.token_addresses)}:")
            logger.debug(f"  Amount in: {normalize_amount(amount, decimals_in):.6f}")
            logger.debug(f"  Tokens bought: {float(tokens_bought_normalized):.6f}")
            logger.debug(f"  Token in received: {float(token_in_received_normalized):.6f}")
            logger.debug(f"  Gross profit: {normalize_amount(gross_profit, decimals_in):.6f}")
            logger.debug(f"  Net profit: {normalize_amount(net_profit, decimals_in):.6f}")
            logger.debug(f"  Profit percentage: {float(net_profit_percentage):.4f}%")

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
            # Simplified: assume 30 gwei gas price and MATIC at $0.80
            gas_price_wei = self.w3.to_wei(30, 'gwei')
            gas_cost_matic_wei = gas_units * gas_price_wei

            symbol = get_token_name(token_address, self.token_addresses)

            if symbol == 'WMATIC':
                return gas_cost_matic_wei
            elif symbol in self.stablecoins:
                # Convert MATIC to USD: 1 MATIC = $0.80
                matic_amount = self.w3.from_wei(gas_cost_matic_wei, 'ether')
                usd_amount = matic_amount * Decimal('0.80')
                return int(usd_amount * (10 ** decimals))
            else:
                # For other tokens, rough estimation
                return int(gas_cost_matic_wei * 2)  # Assume token is worth ~0.5 MATIC

        except Exception as e:
            logger.debug(f"Gas cost estimation failed: {e}")
            return int(self.w3.to_wei(5, 'ether'))  # Default 5 MATIC equivalent

    def get_supported_token_pairs(self) -> List[Tuple[str, str]]:
        """Get supported token pairs for arbitrage."""
        pairs = []
        tokens = list(self.token_addresses.values())

        # Generate all possible pairs
        for i, token_a in enumerate(tokens):
            for token_b in tokens[i + 1:]:
                pairs.append((token_a, token_b))
                pairs.append((token_b, token_a))  # Both directions

        return pairs

    def get_trade_amounts(self) -> List[int]:
        """Get trade amounts to test."""
        return self.default_amounts.copy()

    async def validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate that an opportunity is still profitable."""
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

            # Recalculate profit
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
        """Get health status of price feeds."""
        status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'dex_status': {},
            'cache_size': len(self.price_cache),
            'enabled_dexes': self.enabled_dexes
        }

        try:
            # Test each DEX
            test_token_in = list(self.token_addresses.values())[0]
            test_token_out = list(self.token_addresses.values())[1]
            test_amount = self.default_amounts[0]

            for dex in self.enabled_dexes:
                try:
                    quote = await self.get_price_quote(dex, test_token_in, test_token_out, test_amount)
                    status['dex_status'][dex] = {
                        'status': 'healthy' if quote else 'warning',
                        'last_quote_time': quote.timestamp.isoformat() if quote else None
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
        self.cache_ttl = max(10, min(300, ttl_seconds))  # Between 10s and 5min
        logger.info(f"Price cache TTL set to {self.cache_ttl} seconds")

    async def test_price_feeds(self) -> Dict:
        """Test price feeds functionality."""
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'passed',
            'tests': {}
        }

        try:
            # Test 1: Basic quote fetching
            tokens = list(self.token_addresses.values())[:2]
            test_amount = self.default_amounts[0]

            quote = await self.get_price_quote(
                self.enabled_dexes[0], tokens[0], tokens[1], test_amount
            )

            test_results['tests']['quote_fetching'] = {
                'status': 'passed' if quote else 'failed',
                'dex_tested': self.enabled_dexes[0],
                'quote_valid': quote.is_valid if quote else False
            }

            # Test 2: Price validation
            if quote:
                is_valid = self._validate_quote(quote, tokens[0], tokens[1])
                test_results['tests']['price_validation'] = {
                    'status': 'passed' if is_valid else 'failed',
                    'price': float(quote.price),
                    'validation_passed': is_valid
                }

            # Test 3: Arbitrage opportunity detection
            token_pairs = [(tokens[0], tokens[1])]
            opportunities = await self.find_arbitrage_opportunities(
                token_pairs, [test_amount]
            )

            test_results['tests']['arbitrage_detection'] = {
                'status': 'passed',
                'opportunities_found': len(opportunities),
                'profitable_opportunities': len([op for op in opportunities
                                                 if op.profit_percentage > 0])
            }

            # Test 4: Stablecoin price validation
            stablecoin_addresses = [addr for symbol, addr in self.token_addresses.items()
                                    if symbol in self.stablecoins]

            if len(stablecoin_addresses) >= 2:
                stablecoin_quote = await self.get_price_quote(
                    self.enabled_dexes[0], stablecoin_addresses[0],
                    stablecoin_addresses[1], test_amount
                )

                if stablecoin_quote:
                    price_reasonable = (Decimal('0.95') <= stablecoin_quote.price <= Decimal('1.05'))
                    test_results['tests']['stablecoin_validation'] = {
                        'status': 'passed' if price_reasonable else 'failed',
                        'price': float(stablecoin_quote.price),
                        'price_reasonable': price_reasonable
                    }

            # Overall status
            failed_tests = [test for test, results in test_results['tests'].items()
                            if results['status'] == 'failed']

            if failed_tests:
                test_results['overall_status'] = 'failed'
                test_results['failed_tests'] = failed_tests

        except Exception as e:
            test_results['overall_status'] = 'error'
            test_results['error'] = str(e)

        return test_results

    def get_price_feed_summary(self) -> Dict:
        """Get a summary of price feed configuration and status."""
        return {
            'configuration': {
                'enabled_dexes': self.enabled_dexes,
                'monitored_tokens': len(self.token_addresses),
                'stablecoins': list(self.stablecoins),
                'default_amounts': [self.w3.from_wei(amt, 'ether') for amt in self.default_amounts],
                'cache_ttl': self.cache_ttl
            },
            'runtime_stats': {
                'cached_quotes': len(self.price_cache),
                'gas_estimates': self.gas_estimates
            },
            'dex_configs': {dex: config['name'] for dex, config in self.dex_configs.items()},
            'token_addresses': {symbol: addr[:10] + "..." for symbol, addr in self.token_addresses.items()}
        }