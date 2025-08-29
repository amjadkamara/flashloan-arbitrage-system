# Price data aggregation 
# bot/price_feeds.py
"""
Price Feeds - Multi-Source Price Aggregation

This module aggregates price data from multiple sources including:
- 1inch API for swap quotes and prices
- DEX on-chain price queries
- CoinGecko API for reference prices
- Custom price oracles

Provides real-time price feeds for arbitrage opportunity detection.
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from web3 import Web3
from web3.contract import Contract

from config.settings import Settings
from config.addresses import POLYGON_ADDRESSES, DEX_ADDRESSES
from .utils.helpers import format_amount, calculate_slippage
from .utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)


@dataclass
class PriceQuote:
    """Represents a price quote from a DEX or aggregator."""
    dex: str
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    gas_estimate: int
    price: Decimal
    slippage: Decimal
    timestamp: datetime
    route_data: Dict[str, Any]


@dataclass
class ArbitrageOpportunity:
    """Represents a potential arbitrage opportunity."""
    token_in: str
    token_out: str
    amount: int
    buy_dex: str
    sell_dex: str
    buy_price: Decimal
    sell_price: Decimal
    profit_percentage: Decimal
    estimated_profit: int
    gas_cost: int
    net_profit: int
    route_data: Dict[str, Any]


class PriceFeeds:
    """
    Aggregates price data from multiple sources for arbitrage detection.

    Features:
    - 1inch API integration for best swap routes
    - Multiple DEX price comparison
    - Real-time price monitoring
    - Arbitrage opportunity detection
    - Slippage and gas cost calculation
    - Price impact analysis
    """

    def __init__(self, settings: Settings, w3: Web3):
        """Initialize price feeds with API connections."""
        self.settings = settings
        self.w3 = w3

        # API configuration
        self.oneinch_base_url = "https://api.1inch.dev"
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.chain_id = 137  # Polygon

        # Rate limiting
        self.last_api_call = {}
        self.min_api_interval = 1.0  # Minimum seconds between API calls

        # Price cache
        self.price_cache = {}
        self.cache_duration = 30  # Cache prices for 30 seconds

        # Supported tokens
        self.supported_tokens = POLYGON_ADDRESSES
        self.dex_routers = DEX_ADDRESSES

        # Session for HTTP requests
        self.session = None

        logger.info("PriceFeeds initialized")
        logger.info(f"Monitoring {len(self.supported_tokens)} tokens across {len(self.dex_routers)} DEXs")

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Authorization': f'Bearer {self.settings.api.oneinch_api_key}',
                'Content-Type': 'application/json'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def get_1inch_quote(
            self,
            token_in: str,
            token_out: str,
            amount: int,
            slippage: float = 1.0
    ) -> Optional[PriceQuote]:
        """
        Get swap quote from 1inch API.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap (in wei)
            slippage: Maximum slippage percentage

        Returns:
            PriceQuote object or None if failed
        """
        try:
            # Rate limiting check
            api_key = "1inch_quote"
            if not self._can_make_api_call(api_key):
                return None

            # Build API URL
            url = f"{self.oneinch_base_url}/swap/v6.0/{self.chain_id}/quote"
            params = {
                'src': token_in,
                'dst': token_out,
                'amount': str(amount),
                'includeProtocols': 'true',
                'includeGas': 'true'
            }

            # Make API request
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # Parse response
                    amount_out = int(data['dstAmount'])
                    gas_estimate = int(data.get('gas', 200000))
                    protocols = data.get('protocols', [])

                    # Calculate price
                    price = Decimal(amount_out) / Decimal(amount)

                    quote = PriceQuote(
                        dex="1inch",
                        token_in=token_in,
                        token_out=token_out,
                        amount_in=amount,
                        amount_out=amount_out,
                        gas_estimate=gas_estimate,
                        price=price,
                        slippage=Decimal(slippage),
                        timestamp=datetime.now(),
                        route_data={
                            'protocols': protocols,
                            'tx_data': data.get('tx', {})
                        }
                    )

                    logger.debug(f"1inch quote: {format_amount(amount, 18)} -> {format_amount(amount_out, 18)}")
                    return quote

                else:
                    logger.warning(f"1inch API error: {response.status}")

        except Exception as e:
            logger.error(f"Failed to get 1inch quote: {e}")

        return None

    async def get_dex_quotes(
            self,
            token_in: str,
            token_out: str,
            amount: int
    ) -> List[PriceQuote]:
        """
        Get quotes from multiple DEXs.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap (in wei)

        Returns:
            List of PriceQuote objects from different DEXs
        """
        quotes = []

        # Get 1inch quote (aggregated)
        oneinch_quote = await self.get_1inch_quote(token_in, token_out, amount)
        if oneinch_quote:
            quotes.append(oneinch_quote)

        # Get individual DEX quotes (if needed for comparison)
        dex_tasks = []
        for dex_name, router_address in self.dex_routers.items():
            if dex_name != "1INCH":  # Skip 1inch as we already got it
                task = self._get_dex_quote(dex_name, router_address, token_in, token_out, amount)
                dex_tasks.append(task)

        # Execute DEX queries concurrently
        if dex_tasks:
            dex_results = await asyncio.gather(*dex_tasks, return_exceptions=True)
            for result in dex_results:
                if isinstance(result, PriceQuote):
                    quotes.append(result)

        logger.debug(f"Retrieved {len(quotes)} quotes for {token_in[:8]}... -> {token_out[:8]}...")
        return quotes

    async def _get_dex_quote(
            self,
            dex_name: str,
            router_address: str,
            token_in: str,
            token_out: str,
            amount: int
    ) -> Optional[PriceQuote]:
        """Get quote from a specific DEX router."""
        try:
            # This would implement specific DEX quote logic
            # For now, we'll focus on 1inch as the primary source
            # Individual DEX implementations can be added later
            pass

        except Exception as e:
            logger.debug(f"Failed to get {dex_name} quote: {e}")

        return None

    async def find_arbitrage_opportunities(
            self,
            token_pairs: List[Tuple[str, str]],
            amounts: List[int]
    ) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities across token pairs and amounts.

        Args:
            token_pairs: List of (token_in, token_out) pairs to check
            amounts: List of trade amounts to test

        Returns:
            List of profitable ArbitrageOpportunity objects
        """
        opportunities = []

        for token_in, token_out in token_pairs:
            for amount in amounts:
                # Get quotes for this pair and amount
                quotes = await self.get_dex_quotes(token_in, token_out, amount)

                if len(quotes) >= 2:
                    # Find best buy and sell prices
                    best_buy = min(quotes, key=lambda q: q.price)  # Lowest price to buy
                    best_sell = max(quotes, key=lambda q: q.price)  # Highest price to sell

                    # Calculate potential profit
                    if best_sell.price > best_buy.price:
                        profit_pct = (best_sell.price - best_buy.price) / best_buy.price * 100

                        # Estimate gas costs
                        gas_cost = self._estimate_arbitrage_gas_cost(
                            best_buy.gas_estimate + best_sell.gas_estimate + 100000  # Base flashloan gas
                        )

                        # Calculate estimated profit in wei
                        amount_out_buy = int(amount * best_buy.price)
                        amount_out_sell = int(amount_out_buy * best_sell.price)
                        estimated_profit = amount_out_sell - amount - gas_cost

                        # Check if profitable
                        if profit_pct >= self.settings.trading.min_profit_threshold and estimated_profit > 0:
                            opportunity = ArbitrageOpportunity(
                                token_in=token_in,
                                token_out=token_out,
                                amount=amount,
                                buy_dex=best_buy.dex,
                                sell_dex=best_sell.dex,
                                buy_price=best_buy.price,
                                sell_price=best_sell.price,
                                profit_percentage=Decimal(str(profit_pct)),
                                estimated_profit=estimated_profit,
                                gas_cost=gas_cost,
                                net_profit=estimated_profit - gas_cost,
                                route_data={
                                    'buy_route': best_buy.route_data,
                                    'sell_route': best_sell.route_data
                                }
                            )

                            opportunities.append(opportunity)

                            logger.info(f"Arbitrage opportunity found:")
                            logger.info(f"  {token_in[:8]}... -> {token_out[:8]}...")
                            logger.info(f"  Buy on {best_buy.dex}, Sell on {best_sell.dex}")
                            logger.info(f"  Profit: {profit_pct:.2f}% ({format_amount(estimated_profit, 18)} MATIC)")

        return sorted(opportunities, key=lambda x: x.profit_percentage, reverse=True)

    def _estimate_arbitrage_gas_cost(self, total_gas: int) -> int:
        """Estimate gas cost in wei for arbitrage transaction."""
        gas_price = self.w3.eth.gas_price
        return total_gas * gas_price

    async def get_token_price_usd(self, token_address: str) -> Optional[Decimal]:
        """
        Get token price in USD from CoinGecko.

        Args:
            token_address: Token contract address

        Returns:
            Price in USD or None if failed
        """
        try:
            # Check cache first
            cache_key = f"usd_price_{token_address}"
            cached_price = self._get_cached_price(cache_key)
            if cached_price:
                return cached_price

            # Rate limiting check
            if not self._can_make_api_call("coingecko"):
                return None

            # Map token address to CoinGecko ID (simplified mapping)
            token_ids = {
                self.supported_tokens['MATIC']: 'matic-network',
                self.supported_tokens['USDC']: 'usd-coin',
                self.supported_tokens['USDT']: 'tether',
                self.supported_tokens['WETH']: 'ethereum',
                self.supported_tokens['WBTC']: 'wrapped-bitcoin'
            }

            token_id = token_ids.get(token_address.lower())
            if not token_id:
                return None

            # Make API request
            url = f"{self.coingecko_base_url}/simple/price"
            params = {
                'ids': token_id,
                'vs_currencies': 'usd'
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price = Decimal(str(data[token_id]['usd']))

                    # Cache the price
                    self._cache_price(cache_key, price)

                    return price

        except Exception as e:
            logger.error(f"Failed to get USD price for {token_address}: {e}")

        return None

    async def monitor_prices(
            self,
            token_pairs: List[Tuple[str, str]],
            amounts: List[int],
            callback=None
    ) -> None:
        """
        Continuously monitor prices for arbitrage opportunities.

        Args:
            token_pairs: List of token pairs to monitor
            amounts: List of trade amounts to check
            callback: Optional callback function for opportunities
        """
        logger.info(f"Starting price monitoring for {len(token_pairs)} pairs")

        while True:
            try:
                # Find opportunities
                opportunities = await self.find_arbitrage_opportunities(token_pairs, amounts)

                if opportunities:
                    logger.info(f"Found {len(opportunities)} arbitrage opportunities")

                    # Call callback if provided
                    if callback:
                        for opportunity in opportunities:
                            await callback(opportunity)
                else:
                    logger.debug("No arbitrage opportunities found")

                # Wait before next check
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in price monitoring: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    def _can_make_api_call(self, api_key: str) -> bool:
        """Check if we can make an API call (rate limiting)."""
        now = datetime.now()
        last_call = self.last_api_call.get(api_key)

        if not last_call or (now - last_call).total_seconds() >= self.min_api_interval:
            self.last_api_call[api_key] = now
            return True

        return False

    def _get_cached_price(self, cache_key: str) -> Optional[Decimal]:
        """Get cached price if still valid."""
        if cache_key in self.price_cache:
            price_data = self.price_cache[cache_key]
            if datetime.now() - price_data['timestamp'] < timedelta(seconds=self.cache_duration):
                return price_data['price']

        return None

    def _cache_price(self, cache_key: str, price: Decimal) -> None:
        """Cache a price with timestamp."""
        self.price_cache[cache_key] = {
            'price': price,
            'timestamp': datetime.now()
        }

    async def get_swap_data_for_1inch(
            self,
            token_in: str,
            token_out: str,
            amount: int,
            slippage: float = 1.0,
            from_address: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete swap transaction data from 1inch API.

        Args:
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap
            slippage: Slippage tolerance
            from_address: Address to execute swap from

        Returns:
            Complete transaction data for the swap
        """
        try:
            # Rate limiting check
            if not self._can_make_api_call("1inch_swap"):
                return None

            # Build API URL
            url = f"{self.oneinch_base_url}/swap/v6.0/{self.chain_id}/swap"
            params = {
                'src': token_in,
                'dst': token_out,
                'amount': str(amount),
                'from': from_address or '',
                'slippage': str(slippage),
                'disableEstimate': 'false'
            }

            # Make API request
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    logger.debug(f"1inch swap data retrieved for {format_amount(amount, 18)} tokens")
                    return data
                else:
                    error_text = await response.text()
                    logger.warning(f"1inch swap API error {response.status}: {error_text}")

        except Exception as e:
            logger.error(f"Failed to get 1inch swap data: {e}")

        return None

    async def validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Validate an arbitrage opportunity before execution.

        Args:
            opportunity: The arbitrage opportunity to validate

        Returns:
            True if opportunity is still valid
        """
        try:
            # Re-check prices to ensure opportunity still exists
            current_quotes = await self.get_dex_quotes(
                opportunity.token_in,
                opportunity.token_out,
                opportunity.amount
            )

            if len(current_quotes) < 2:
                logger.warning("Not enough quotes to validate opportunity")
                return False

            # Find current best prices
            current_best_buy = min(current_quotes, key=lambda q: q.price)
            current_best_sell = max(current_quotes, key=lambda q: q.price)

            # Check if profit is still above threshold
            current_profit_pct = (current_best_sell.price - current_best_buy.price) / current_best_buy.price * 100

            if current_profit_pct >= self.settings.trading.min_profit_threshold:
                logger.info(f"Opportunity validated: {current_profit_pct:.2f}% profit")
                return True
            else:
                logger.info(f"Opportunity expired: only {current_profit_pct:.2f}% profit")
                return False

        except Exception as e:
            logger.error(f"Failed to validate opportunity: {e}")
            return False

    def get_supported_token_pairs(self) -> List[Tuple[str, str]]:
        """Get list of supported token pairs for arbitrage."""
        tokens = list(self.supported_tokens.values())
        pairs = []

        # Generate all possible pairs
        for i, token_a in enumerate(tokens):
            for token_b in tokens[i + 1:]:
                pairs.append((token_a, token_b))
                pairs.append((token_b, token_a))  # Both directions

        logger.info(f"Generated {len(pairs)} token pairs for monitoring")
        return pairs

    def get_trade_amounts(self) -> List[int]:
        """Get list of trade amounts to test for arbitrage."""
        base_amounts = [100, 500, 1000, 2500, 5000, 10000]  # In MATIC
        amounts_wei = []

        for amount_matic in base_amounts:
            if (100 <= amount_matic <=
                    self.settings.trading.max_trade_size):
                amounts_wei.append(self.w3.to_wei(amount_matic, 'ether'))

        logger.info(f"Testing {len(amounts_wei)} different trade amounts")
        return amounts_wei

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of price feeds."""
        try:
            # Test API connectivity
            oneinch_status = await self._test_1inch_api()
            coingecko_status = await self._test_coingecko_api()

            return {
                'status': 'healthy' if oneinch_status and coingecko_status else 'degraded',
                'apis': {
                    '1inch': oneinch_status,
                    'coingecko': coingecko_status
                },
                'cache_size': len(self.price_cache),
                'supported_tokens': len(self.supported_tokens),
                'dex_routers': len(self.dex_routers)
            }

        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {'status': 'error', 'error': str(e)}

    async def _test_1inch_api(self) -> bool:
        """Test 1inch API connectivity."""
        try:
            url = f"{self.oneinch_base_url}/healthcheck"
            async with self.session.get(url) as response:
                return response.status == 200
        except:
            return False

    async def _test_coingecko_api(self) -> bool:
        """Test CoinGecko API connectivity."""
        try:
            url = f"{self.coingecko_base_url}/ping"
            async with self.session.get(url) as response:
                return response.status == 200
        except:
            return False

    def __str__(self) -> str:
        """String representation of PriceFeeds."""
        return f"PriceFeeds(tokens={len(self.supported_tokens)}, dexs={len(self.dex_routers)})"