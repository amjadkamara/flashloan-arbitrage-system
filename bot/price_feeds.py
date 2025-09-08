# bot/price_feeds.py
"""
Price Feeds - Multi-Source Price Aggregation (CORRECTED VERSION)
Fixed gas calculation and arbitrage math for Polygon network
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math

from web3 import Web3
from web3.contract import Contract

from config.settings import Settings
from config.addresses import POLYGON_ADDRESSES, DEX_ADDRESSES
from .utils.helpers import format_amount, calculate_slippage
from .utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)

# Uniswap V3 ABI (minimal for price quotes)
UNISWAP_V3_QUOTER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "path", "type": "bytes"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"}
        ],
        "name": "quoteExactInput",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160[]", "name": "sqrtPriceX96AfterList", "type": "uint160[]"},
            {"internalType": "uint32[]", "name": "initializedTicksCrossedList", "type": "uint32[]"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# SushiSwap Router ABI (minimal)
SUSHISWAP_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]


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
    Enhanced price aggregator with corrected Polygon calculations.
    """

    def __init__(self, settings: Settings, w3: Web3):
        """Initialize price feeds with DEX contracts."""
        self.settings = settings
        self.w3 = w3

        # API configuration
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.chain_id = 137  # Polygon

        # Rate limiting
        self.last_api_call = {}
        self.min_api_interval = 1.0

        # Price cache
        self.price_cache = {}
        self.cache_duration = 30

        # Supported tokens and DEXs
        self.supported_tokens = POLYGON_ADDRESSES
        self.dex_addresses = DEX_ADDRESSES

        # MATIC price cache for gas calculations
        self.matic_price_usd = Decimal("0.53")  # Default, will be updated
        self.last_matic_price_update = datetime.now()

        # Initialize DEX contracts
        self._init_dex_contracts()

        # Session for HTTP requests
        self.session = None

        logger.info("🔥 Enhanced PriceFeeds initialized with corrected Polygon calculations")
        logger.info(f"📊 Monitoring {len(self.supported_tokens)} tokens across {len(self.active_dexs)} DEXs")

    def _init_dex_contracts(self):
        """Initialize smart contract instances for each DEX."""
        self.active_dexs = {}

        try:
            # Uniswap V3 Quoter
            if 'UNISWAP_V3_QUOTER' in self.dex_addresses:
                self.active_dexs['uniswap_v3'] = {
                    'name': 'Uniswap V3',
                    'contract': self.w3.eth.contract(
                        address=self.dex_addresses['UNISWAP_V3_QUOTER'],
                        abi=UNISWAP_V3_QUOTER_ABI
                    ),
                    'type': 'v3',
                    'fees': [500, 3000, 10000]
                }
                logger.info("✅ Uniswap V3 contract initialized")

            # SushiSwap Router
            if 'SUSHISWAP_ROUTER' in self.dex_addresses:
                self.active_dexs['sushiswap'] = {
                    'name': 'SushiSwap',
                    'contract': self.w3.eth.contract(
                        address=self.dex_addresses['SUSHISWAP_ROUTER'],
                        abi=SUSHISWAP_ROUTER_ABI
                    ),
                    'type': 'v2',
                    'fee': 3000
                }
                logger.info("✅ SushiSwap contract initialized")

            # QuickSwap Router
            if 'QUICKSWAP_ROUTER' in self.dex_addresses:
                self.active_dexs['quickswap'] = {
                    'name': 'QuickSwap',
                    'contract': self.w3.eth.contract(
                        address=self.dex_addresses['QUICKSWAP_ROUTER'],
                        abi=SUSHISWAP_ROUTER_ABI
                    ),
                    'type': 'v2',
                    'fee': 3000
                }
                logger.info("✅ QuickSwap contract initialized")

        except Exception as e:
            logger.error(f"❌ Error initializing DEX contracts: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'Content-Type': 'application/json'}
        )
        # Update MATIC price on startup
        await self._update_matic_price()
        logger.info("🌐 HTTP session started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            logger.info("🌐 HTTP session closed")

    async def _update_matic_price(self):
        """Update MATIC price in USD for gas calculations."""
        try:
            if not self.session:
                return

            # Only update if price is older than 5 minutes
            if (datetime.now() - self.last_matic_price_update).total_seconds() < 300:
                return

            url = f"{self.coingecko_base_url}/simple/price"
            params = {'ids': 'matic-network', 'vs_currencies': 'usd'}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.matic_price_usd = Decimal(str(data['matic-network']['usd']))
                    self.last_matic_price_update = datetime.now()
                    logger.debug(f"Updated MATIC price: ${self.matic_price_usd}")

        except Exception as e:
            logger.debug(f"Failed to update MATIC price: {e}")

    async def get_uniswap_v3_quote(self, token_in: str, token_out: str, amount: int, fee: int = 3000) -> Optional[
        PriceQuote]:
        """Get quote from Uniswap V3."""
        try:
            if 'uniswap_v3' not in self.active_dexs:
                return None

            contract = self.active_dexs['uniswap_v3']['contract']

            # Encode the path for V3
            path = token_in.lower().replace('0x', '')
            path += format(fee, '06x')
            path += token_out.lower().replace('0x', '')
            path_bytes = bytes.fromhex(path)

            # Call the quoter
            result = contract.functions.quoteExactInput(path_bytes, amount).call()
            amount_out = result[0]
            gas_estimate = result[3] if len(result) > 3 else 180000

            if amount_out > 0:
                price = Decimal(amount_out) / Decimal(amount)

                return PriceQuote(
                    dex='uniswap_v3',
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount,
                    amount_out=amount_out,
                    gas_estimate=gas_estimate,
                    price=price,
                    slippage=Decimal('0.005'),
                    timestamp=datetime.now(),
                    route_data={'fee': fee, 'path': path}
                )

        except Exception as e:
            logger.debug(f"Uniswap V3 quote failed for {token_in[:8]}.../{token_out[:8]}...: {e}")

        return None

    async def get_sushiswap_quote(self, token_in: str, token_out: str, amount: int) -> Optional[PriceQuote]:
        """Get quote from SushiSwap."""
        try:
            if 'sushiswap' not in self.active_dexs:
                return None

            contract = self.active_dexs['sushiswap']['contract']
            path = [token_in, token_out]

            amounts = contract.functions.getAmountsOut(amount, path).call()
            amount_out = amounts[-1]

            if amount_out > 0:
                price = Decimal(amount_out) / Decimal(amount)

                return PriceQuote(
                    dex='sushiswap',
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount,
                    amount_out=amount_out,
                    gas_estimate=150000,
                    price=price,
                    slippage=Decimal('0.005'),
                    timestamp=datetime.now(),
                    route_data={'path': path}
                )

        except Exception as e:
            logger.debug(f"SushiSwap quote failed for {token_in[:8]}.../{token_out[:8]}...: {e}")

        return None

    async def get_quickswap_quote(self, token_in: str, token_out: str, amount: int) -> Optional[PriceQuote]:
        """Get quote from QuickSwap."""
        try:
            if 'quickswap' not in self.active_dexs:
                return None

            contract = self.active_dexs['quickswap']['contract']
            path = [token_in, token_out]

            amounts = contract.functions.getAmountsOut(amount, path).call()
            amount_out = amounts[-1]

            if amount_out > 0:
                price = Decimal(amount_out) / Decimal(amount)

                return PriceQuote(
                    dex='quickswap',
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount,
                    amount_out=amount_out,
                    gas_estimate=145000,
                    price=price,
                    slippage=Decimal('0.005'),
                    timestamp=datetime.now(),
                    route_data={'path': path}
                )

        except Exception as e:
            logger.debug(f"QuickSwap quote failed for {token_in[:8]}.../{token_out[:8]}...: {e}")

        return None

    async def get_dex_quotes(self, token_in: str, token_out: str, amount: int) -> List[PriceQuote]:
        """Get quotes from all available DEXs."""
        quotes = []
        tasks = []

        # Uniswap V3 (try multiple fee tiers)
        if 'uniswap_v3' in self.active_dexs:
            for fee in [500, 3000, 10000]:
                tasks.append(self.get_uniswap_v3_quote(token_in, token_out, amount, fee))

        # SushiSwap
        if 'sushiswap' in self.active_dexs:
            tasks.append(self.get_sushiswap_quote(token_in, token_out, amount))

        # QuickSwap
        if 'quickswap' in self.active_dexs:
            tasks.append(self.get_quickswap_quote(token_in, token_out, amount))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, PriceQuote):
                    quotes.append(result)

        logger.debug(f"Retrieved {len(quotes)} quotes for {token_in[:8]}...→{token_out[:8]}...")
        return quotes

    def _calculate_gas_cost_usd(self, total_gas: int) -> Decimal:
        """Calculate gas cost in USD properly for Polygon."""
        try:
            # Get current gas price in wei
            gas_price = self.w3.eth.gas_price

            # Calculate gas cost in MATIC
            gas_cost_wei = total_gas * gas_price
            gas_cost_matic = Decimal(gas_cost_wei) / Decimal(10 ** 18)

            # Convert to USD using MATIC price
            gas_cost_usd = gas_cost_matic * self.matic_price_usd

            return gas_cost_usd

        except Exception as e:
            logger.debug(f"Gas calculation error: {e}")
            # Fallback: assume 0.01 MATIC gas cost
            return Decimal("0.01") * self.matic_price_usd

    async def find_arbitrage_opportunities(self, token_pairs: List[Tuple[str, str]], amounts: List[int]) -> List[
        ArbitrageOpportunity]:
        """Find arbitrage opportunities with corrected calculations."""
        opportunities = []

        logger.info(f"🔍 Scanning {len(token_pairs)} pairs with {len(amounts)} amounts...")

        # Update MATIC price before calculating
        await self._update_matic_price()

        for token_in, token_out in token_pairs:
            for amount in amounts:
                try:
                    quotes = await self.get_dex_quotes(token_in, token_out, amount)

                    if len(quotes) >= 2:
                        best_buy = min(quotes, key=lambda q: q.price)
                        best_sell = max(quotes, key=lambda q: q.price)

                        if best_buy.dex == best_sell.dex:
                            continue

                        # CORRECTED ARBITRAGE CALCULATION
                        # Step 1: Calculate price difference percentage
                        price_difference = best_sell.price - best_buy.price

                        if price_difference > 0:
                            profit_percentage = (price_difference / best_buy.price) * 100

                            # Step 2: Calculate estimated profit in token_in units
                            # This is the extra amount we get back from the arbitrage
                            estimated_profit_ratio = price_difference / best_buy.price
                            estimated_profit = int(amount * estimated_profit_ratio)

                            # Step 3: Calculate gas cost in USD (CORRECTED)
                            total_gas = best_buy.gas_estimate + best_sell.gas_estimate + 100000  # flashloan overhead
                            gas_cost_usd = self._calculate_gas_cost_usd(total_gas)

                            # Step 4: Convert estimated profit to USD for comparison
                            if token_in == self.supported_tokens['USDC']:
                                estimated_profit_usd = Decimal(estimated_profit) / Decimal(10 ** 6)
                            elif token_in == self.supported_tokens['USDT']:
                                estimated_profit_usd = Decimal(estimated_profit) / Decimal(10 ** 6)
                            else:
                                # For other tokens, assume 18 decimals and use current price
                                estimated_profit_usd = Decimal(estimated_profit) / Decimal(
                                    10 ** 18) * self.matic_price_usd

                            # Step 5: Calculate net profit in USD
                            net_profit_usd = estimated_profit_usd - gas_cost_usd

                            # Step 6: Check profitability with realistic thresholds
                            min_profit_percentage = Decimal("0.1")  # 0.1%
                            min_profit_usd = Decimal("0.50")  # $0.50 minimum

                            if (profit_percentage >= min_profit_percentage and
                                    estimated_profit > 0 and
                                    net_profit_usd >= min_profit_usd):
                                opportunity = ArbitrageOpportunity(
                                    token_in=token_in,
                                    token_out=token_out,
                                    amount=amount,
                                    buy_dex=best_buy.dex,
                                    sell_dex=best_sell.dex,
                                    buy_price=best_buy.price,
                                    sell_price=best_sell.price,
                                    profit_percentage=Decimal(str(profit_percentage)),
                                    estimated_profit=estimated_profit,
                                    gas_cost=int(gas_cost_usd * 10 ** 6),  # Store as USDC units
                                    net_profit=int(net_profit_usd * 10 ** 6),  # Store as USDC units
                                    route_data={
                                        'buy_route': best_buy.route_data,
                                        'sell_route': best_sell.route_data
                                    }
                                )

                                opportunities.append(opportunity)

                                logger.info(f"💎 OPPORTUNITY FOUND:")
                                logger.info(
                                    f"   {self._get_token_symbol(token_in)} → {self._get_token_symbol(token_out)}")
                                logger.info(f"   Buy: {best_buy.dex} | Sell: {best_sell.dex}")
                                logger.info(f"   Profit: {profit_percentage:.3f}% (${net_profit_usd:.2f} net)")
                                logger.info(f"   Gas cost: ${gas_cost_usd:.3f}")

                except Exception as e:
                    logger.debug(f"Error processing {token_in[:8]}.../{token_out[:8]}...: {e}")

                await asyncio.sleep(0.1)

        logger.info(f"🎯 Found {len(opportunities)} profitable opportunities")
        return sorted(opportunities, key=lambda x: x.profit_percentage, reverse=True)

    def _get_token_symbol(self, address: str) -> str:
        """Get token symbol from address."""
        symbol_map = {v.lower(): k for k, v in self.supported_tokens.items()}
        return symbol_map.get(address.lower(), f"{address[:6]}...")

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

    def get_supported_token_pairs(self) -> List[Tuple[str, str]]:
        """Get list of supported token pairs for arbitrage."""
        major_tokens = [
            self.supported_tokens['USDC'],
            self.supported_tokens['USDT'],
            self.supported_tokens['WETH'],
            self.supported_tokens['WMATIC'],
            self.supported_tokens['DAI']
        ]

        pairs = []
        for i, token_a in enumerate(major_tokens):
            for token_b in major_tokens[i + 1:]:
                pairs.append((token_a, token_b))
                pairs.append((token_b, token_a))

        logger.info(f"📊 Generated {len(pairs)} high-liquidity token pairs")
        return pairs

    def get_trade_amounts(self) -> List[int]:
        """Get list of trade amounts to test for arbitrage."""
        base_amounts = [100, 500, 1000, 2500, 5000]
        amounts_wei = []

        for amount_usd in base_amounts:
            amount_wei = amount_usd * 10 ** 6  # USDC format
            amounts_wei.append(amount_wei)

        logger.info(f"💰 Testing {len(amounts_wei)} trade amounts: ${base_amounts}")
        return amounts_wei

    async def validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate an arbitrage opportunity before execution."""
        try:
            current_quotes = await self.get_dex_quotes(
                opportunity.token_in,
                opportunity.token_out,
                opportunity.amount
            )

            if len(current_quotes) < 2:
                return False

            current_best_buy = min(current_quotes, key=lambda q: q.price)
            current_best_sell = max(current_quotes, key=lambda q: q.price)

            current_profit_pct = (current_best_sell.price - current_best_buy.price) / current_best_buy.price * 100

            return current_profit_pct >= 0.1

        except Exception as e:
            logger.error(f"Failed to validate opportunity: {e}")
            return False

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of price feeds."""
        try:
            dex_status = {}
            for dex_name, dex_info in self.active_dexs.items():
                try:
                    if dex_info['type'] == 'v2':
                        test_amount = 1000000
                        test_path = [self.supported_tokens['USDC'], self.supported_tokens['WETH']]
                        result = dex_info['contract'].functions.getAmountsOut(test_amount, test_path).call()
                        dex_status[dex_name] = 'healthy' if result[1] > 0 else 'degraded'
                    else:
                        dex_status[dex_name] = 'healthy'
                except:
                    dex_status[dex_name] = 'error'

            return {
                'status': 'healthy' if all(status != 'error' for status in dex_status.values()) else 'degraded',
                'dexs': dex_status,
                'active_dexs': len(self.active_dexs),
                'matic_price': str(self.matic_price_usd),
                'cache_size': len(self.price_cache)
            }

        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {'status': 'error', 'error': str(e)}

    def __str__(self) -> str:
        """String representation of PriceFeeds."""
        return f"PriceFeeds(tokens={len(self.supported_tokens)}, dexs={len(self.active_dexs)})"
