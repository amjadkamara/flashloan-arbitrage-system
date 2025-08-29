# Price difference detection 
# bot/opportunity_scanner.py
"""
Opportunity Scanner - Price Difference Detection

This module continuously scans for arbitrage opportunities across multiple DEXs
by comparing prices, analyzing spreads, and identifying profitable trades.
It works closely with PriceFeeds to get real-time market data.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
from collections import defaultdict

from web3 import Web3

from config.settings import Settings
from .price_feeds import PriceFeeds, ArbitrageOpportunity, PriceQuote
from .utils.helpers import format_amount, calculate_profit_percentage
from .utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)


@dataclass
class OpportunityMetrics:
    """Metrics for tracking opportunity scanner performance."""
    total_scans: int = 0
    opportunities_found: int = 0
    opportunities_executed: int = 0
    avg_profit_percentage: Decimal = Decimal(0)
    best_profit_percentage: Decimal = Decimal(0)
    scan_duration_ms: int = 0
    last_scan_time: datetime = None


@dataclass
class TokenPairStats:
    """Statistics for a specific token pair."""
    pair: Tuple[str, str]
    opportunities_count: int = 0
    avg_profit: Decimal = Decimal(0)
    best_profit: Decimal = Decimal(0)
    last_opportunity: datetime = None
    most_profitable_dexs: Tuple[str, str] = ("", "")


class OpportunityScanner:
    """
    Scans for arbitrage opportunities across multiple DEXs.

    Features:
    - Real-time price monitoring across DEXs
    - Profitable opportunity identification
    - Historical opportunity tracking
    - Performance metrics and statistics
    - Adaptive scanning based on market conditions
    - Duplicate opportunity filtering
    - Priority-based opportunity ranking
    """

    def __init__(self, settings: Settings, price_feeds: PriceFeeds, w3: Web3):
        """Initialize the opportunity scanner."""
        self.settings = settings
        self.price_feeds = price_feeds
        self.w3 = w3

        # Scanner configuration
        self.scan_interval = 10
        self.min_profit_threshold = self.settings.trading.min_profit_threshold
        self.max_opportunities_per_scan = 10

        # Tracking and metrics
        self.metrics = OpportunityMetrics()
        self.token_pair_stats: Dict[str, TokenPairStats] = {}
        self.recent_opportunities: List[ArbitrageOpportunity] = []
        self.opportunity_history: List[Dict] = []

        # Filtering and deduplication
        self.seen_opportunities: Set[str] = set()
        self.opportunity_cooldown = 60  # seconds

        # Token pairs and amounts to monitor
        self.monitored_pairs = self.price_feeds.get_supported_token_pairs()
        self.trade_amounts = self.price_feeds.get_trade_amounts()

        # Performance optimization
        self.adaptive_scanning = True
        self.high_frequency_pairs: Set[str] = set()
        self.scan_priority_queue = []

        logger.info("OpportunityScanner initialized")
        logger.info(f"Monitoring {len(self.monitored_pairs)} token pairs")
        logger.info(f"Testing {len(self.trade_amounts)} trade amounts")
        logger.info(f"Minimum profit threshold: {self.min_profit_threshold}%")

    async def start_scanning(self, callback=None) -> None:
        """
        Start continuous opportunity scanning.

        Args:
            callback: Optional callback function for new opportunities
        """
        logger.info("Starting opportunity scanning...")

        scan_count = 0
        while True:
            try:
                scan_start = datetime.now()

                # Perform opportunity scan
                opportunities = await self.scan_for_opportunities()

                # Update metrics
                scan_duration = (datetime.now() - scan_start).total_seconds() * 1000
                self.metrics.total_scans += 1
                self.metrics.scan_duration_ms = int(scan_duration)
                self.metrics.last_scan_time = scan_start

                if opportunities:
                    logger.info(f"Scan #{scan_count + 1}: Found {len(opportunities)} opportunities")

                    # Process new opportunities
                    for opportunity in opportunities:
                        if await self._is_new_opportunity(opportunity):
                            # Add to recent opportunities
                            self.recent_opportunities.append(opportunity)
                            self._update_opportunity_stats(opportunity)

                            # Execute callback if provided
                            if callback:
                                try:
                                    await callback(opportunity)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")

                    # Keep only recent opportunities (last 100)
                    self.recent_opportunities = self.recent_opportunities[-100:]
                else:
                    logger.debug(f"Scan #{scan_count + 1}: No opportunities found")

                scan_count += 1

                # Adaptive scanning interval
                sleep_time = self._calculate_adaptive_interval(opportunities)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in opportunity scanning: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    async def scan_for_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Perform a single scan for arbitrage opportunities.

        Returns:
            List of profitable arbitrage opportunities
        """
        opportunities = []

        try:
            # Use priority pairs if available, otherwise all pairs
            pairs_to_scan = self._get_priority_pairs() if self.adaptive_scanning else self.monitored_pairs

            # Get all opportunities from price feeds
            all_opportunities = await self.price_feeds.find_arbitrage_opportunities(
                pairs_to_scan,
                self.trade_amounts
            )

            # Filter and rank opportunities
            filtered_opportunities = await self._filter_opportunities(all_opportunities)
            ranked_opportunities = self._rank_opportunities(filtered_opportunities)

            # Limit number of opportunities per scan
            opportunities = ranked_opportunities[:self.max_opportunities_per_scan]

            # Update metrics
            if opportunities:
                self.metrics.opportunities_found += len(opportunities)
                profits = [op.profit_percentage for op in opportunities]
                self.metrics.avg_profit_percentage = sum(profits) / len(profits)
                self.metrics.best_profit_percentage = max(profits)

            return opportunities

        except Exception as e:
            logger.error(f"Failed to scan for opportunities: {e}")
            return []

    async def _filter_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> List[ArbitrageOpportunity]:
        """Filter opportunities based on various criteria."""
        filtered = []

        for opportunity in opportunities:
            # Basic profit threshold check
            if opportunity.profit_percentage < self.min_profit_threshold:
                continue

            # Gas cost profitability check
            if opportunity.net_profit <= 0:
                continue

            # Trade amount limits check
            amount_matic = self.w3.from_wei(opportunity.amount, 'ether')
            if not (Decimal("100") <= amount_matic <= self.settings.trading.max_trade_size):
                continue

            # Duplicate/cooldown check
            opportunity_key = self._get_opportunity_key(opportunity)
            if opportunity_key in self.seen_opportunities:
                continue

            # Market impact check (simplified)
            if not await self._check_market_impact(opportunity):
                continue

            filtered.append(opportunity)

            # Track seen opportunities
            self.seen_opportunities.add(opportunity_key)

        # Clean up old seen opportunities
        if len(self.seen_opportunities) > 1000:
            self.seen_opportunities.clear()

        return filtered

    def _rank_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> List[ArbitrageOpportunity]:
        """Rank opportunities by profitability and other factors."""

        def score_opportunity(op: ArbitrageOpportunity) -> float:
            """Calculate a score for ranking opportunities."""
            # Base score from profit percentage
            score = float(op.profit_percentage)

            # Bonus for higher absolute profit
            profit_bonus = float(op.net_profit) / 1e18 * 0.1  # Small bonus per MATIC profit
            score += profit_bonus

            # Bonus for frequently profitable pairs
            pair_key = f"{op.token_in}_{op.token_out}"
            if pair_key in self.token_pair_stats:
                stats = self.token_pair_stats[pair_key]
                if stats.opportunities_count > 5:  # Established pair
                    score += 0.5

            # Penalty for high gas cost relative to profit
            gas_cost_matic = float(op.gas_cost) / 1e18
            profit_matic = float(op.net_profit) / 1e18
            if gas_cost_matic > profit_matic * 0.5:  # Gas > 50% of profit
                score -= 1.0

            return score

        return sorted(opportunities, key=score_opportunity, reverse=True)

    async def _is_new_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if this is a genuinely new opportunity."""
        # Simple time-based deduplication
        current_time = datetime.now()

        for recent_op in self.recent_opportunities:
            if (recent_op.token_in == opportunity.token_in and
                    recent_op.token_out == opportunity.token_out and
                    recent_op.amount == opportunity.amount and
                    abs(recent_op.profit_percentage - opportunity.profit_percentage) < 0.1):

                # Same opportunity, check if enough time has passed
                time_diff = (current_time - recent_op.timestamp if hasattr(recent_op, 'timestamp')
                             else timedelta(seconds=0))

                if time_diff.total_seconds() < self.opportunity_cooldown:
                    return False

        return True

    async def _check_market_impact(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if the trade size would cause significant market impact."""
        try:
            # This is a simplified check - in practice, you'd want more sophisticated
            # market impact analysis based on liquidity, order book depth, etc.

            # For now, just check if the trade amount is reasonable relative to
            # typical DEX liquidity (this would need real liquidity data)
            amount_matic = self.w3.from_wei(opportunity.amount, 'ether')

            # Very basic check - trades over 5000 MATIC might have high impact
            if amount_matic > 5000:
                logger.debug(f"Large trade size: {amount_matic} MATIC, checking impact...")
                # Could implement more sophisticated checks here

            return True  # For now, assume all trades are ok

        except Exception as e:
            logger.debug(f"Market impact check failed: {e}")
            return True  # Default to allowing the trade

    def _get_opportunity_key(self, opportunity: ArbitrageOpportunity) -> str:
        """Generate a unique key for opportunity deduplication."""
        return f"{opportunity.token_in}_{opportunity.token_out}_{opportunity.amount}_{opportunity.buy_dex}_{opportunity.sell_dex}"

    def _update_opportunity_stats(self, opportunity: ArbitrageOpportunity) -> None:
        """Update statistics for token pairs."""
        pair_key = f"{opportunity.token_in}_{opportunity.token_out}"

        if pair_key not in self.token_pair_stats:
            self.token_pair_stats[pair_key] = TokenPairStats(
                pair=(opportunity.token_in, opportunity.token_out)
            )

        stats = self.token_pair_stats[pair_key]
        stats.opportunities_count += 1
        stats.last_opportunity = datetime.now()

        # Update average profit
        current_avg = stats.avg_profit
        count = stats.opportunities_count
        stats.avg_profit = (current_avg * (count - 1) + opportunity.profit_percentage) / count

        # Update best profit
        if opportunity.profit_percentage > stats.best_profit:
            stats.best_profit = opportunity.profit_percentage
            stats.most_profitable_dexs = (opportunity.buy_dex, opportunity.sell_dex)

        # Track high-frequency pairs for adaptive scanning
        if stats.opportunities_count >= 5:  # Threshold for "high frequency"
            self.high_frequency_pairs.add(pair_key)

    def _get_priority_pairs(self) -> List[Tuple[str, str]]:
        """Get priority token pairs for adaptive scanning."""
        if not self.high_frequency_pairs:
            return self.monitored_pairs[:20]  # Default to first 20 pairs

        priority_pairs = []
        for pair_key in self.high_frequency_pairs:
            if pair_key in self.token_pair_stats:
                pair = self.token_pair_stats[pair_key].pair
                priority_pairs.append(pair)

        # Add some regular pairs to maintain discovery
        remaining_slots = 20 - len(priority_pairs)
        if remaining_slots > 0:
            other_pairs = [pair for pair in self.monitored_pairs
                           if f"{pair[0]}_{pair[1]}" not in self.high_frequency_pairs]
            priority_pairs.extend(other_pairs[:remaining_slots])

        return priority_pairs

    def _calculate_adaptive_interval(self, opportunities: List[ArbitrageOpportunity]) -> float:
        """Calculate adaptive scanning interval based on market activity."""
        base_interval = self.scan_interval

        if not self.adaptive_scanning:
            return base_interval

        # Faster scanning when opportunities are found
        if opportunities:
            multiplier = max(0.5, 1.0 - len(opportunities) * 0.1)  # Min 0.5x speed
            return base_interval * multiplier

        # Slower scanning during quiet periods
        recent_activity = len([op for op in self.recent_opportunities
                               if hasattr(op, 'timestamp') and
                               (datetime.now() - op.timestamp).total_seconds() < 300])  # Last 5 min

        if recent_activity == 0:
            return base_interval * 2.0  # Slower during quiet periods

        return base_interval

    def get_scanner_metrics(self) -> Dict:
        """Get current scanner performance metrics."""
        return {
            'total_scans': self.metrics.total_scans,
            'opportunities_found': self.metrics.opportunities_found,
            'opportunities_executed': self.metrics.opportunities_executed,
            'avg_profit_percentage': float(self.metrics.avg_profit_percentage),
            'best_profit_percentage': float(self.metrics.best_profit_percentage),
            'scan_duration_ms': self.metrics.scan_duration_ms,
            'last_scan_time': self.metrics.last_scan_time.isoformat() if self.metrics.last_scan_time else None,
            'active_pairs': len(self.high_frequency_pairs),
            'recent_opportunities': len(self.recent_opportunities)
        }

    def get_token_pair_analytics(self) -> Dict:
        """Get analytics for all monitored token pairs."""
        analytics = {}

        for pair_key, stats in self.token_pair_stats.items():
            analytics[pair_key] = {
                'opportunities_count': stats.opportunities_count,
                'avg_profit_percentage': float(stats.avg_profit),
                'best_profit_percentage': float(stats.best_profit),
                'last_opportunity': stats.last_opportunity.isoformat() if stats.last_opportunity else None,
                'most_profitable_dexs': stats.most_profitable_dexs
            }

        return analytics

    def get_recent_opportunities(self, limit: int = 20) -> List[Dict]:
        """Get recent opportunities with details."""
        recent = self.recent_opportunities[-limit:]
        return [self._opportunity_to_dict(op) for op in recent]

    def _opportunity_to_dict(self, opportunity: ArbitrageOpportunity) -> Dict:
        """Convert opportunity to dictionary for JSON serialization."""
        return {
            'token_in': opportunity.token_in,
            'token_out': opportunity.token_out,
            'amount': opportunity.amount,
            'amount_formatted': format_amount(opportunity.amount, 18),
            'buy_dex': opportunity.buy_dex,
            'sell_dex': opportunity.sell_dex,
            'buy_price': float(opportunity.buy_price),
            'sell_price': float(opportunity.sell_price),
            'profit_percentage': float(opportunity.profit_percentage),
            'estimated_profit': opportunity.estimated_profit,
            'estimated_profit_formatted': format_amount(opportunity.estimated_profit, 18),
            'gas_cost': opportunity.gas_cost,
            'net_profit': opportunity.net_profit,
            'net_profit_formatted': format_amount(opportunity.net_profit, 18)
        }

    async def validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Validate an opportunity before execution.

        Args:
            opportunity: The opportunity to validate

        Returns:
            True if the opportunity is still valid
        """
        try:
            # Use price feeds to re-validate the opportunity
            is_valid = await self.price_feeds.validate_opportunity(opportunity)

            if is_valid:
                logger.info(f"Opportunity validated: {opportunity.profit_percentage:.2f}% profit")
                return True
            else:
                logger.info("Opportunity no longer valid")
                return False

        except Exception as e:
            logger.error(f"Failed to validate opportunity: {e}")
            return False

    def mark_opportunity_executed(self, opportunity: ArbitrageOpportunity) -> None:
        """Mark an opportunity as executed for metrics tracking."""
        self.metrics.opportunities_executed += 1

        # Add to history
        self.opportunity_history.append({
            'timestamp': datetime.now().isoformat(),
            'opportunity': self._opportunity_to_dict(opportunity),
            'status': 'executed'
        })

        # Keep history limited
        if len(self.opportunity_history) > 500:
            self.opportunity_history = self.opportunity_history[-400:]

        logger.info(f"Opportunity marked as executed: {opportunity.profit_percentage:.2f}% profit")

    def set_adaptive_scanning(self, enabled: bool) -> None:
        """Enable or disable adaptive scanning."""
        self.adaptive_scanning = enabled
        logger.info(f"Adaptive scanning {'enabled' if enabled else 'disabled'}")

    def set_min_profit_threshold(self, threshold: float) -> None:
        """Update minimum profit threshold."""
        self.min_profit_threshold = threshold
        logger.info(f"Minimum profit threshold updated to {threshold}%")

    def clear_seen_opportunities(self) -> None:
        """Clear the seen opportunities cache."""
        self.seen_opportunities.clear()
        logger.info("Seen opportunities cache cleared")

    def get_top_performing_pairs(self, limit: int = 10) -> List[Dict]:
        """Get the top performing token pairs by average profit."""
        pairs_with_stats = [(pair_key, stats) for pair_key, stats in self.token_pair_stats.items()
                            if stats.opportunities_count >= 3]  # At least 3 opportunities

        # Sort by average profit
        top_pairs = sorted(pairs_with_stats, key=lambda x: x[1].avg_profit, reverse=True)[:limit]

        result = []
        for pair_key, stats in top_pairs:
            result.append({
                'pair': pair_key,
                'token_in': stats.pair[0][:8] + "...",
                'token_out': stats.pair[1][:8] + "...",
                'opportunities_count': stats.opportunities_count,
                'avg_profit_percentage': float(stats.avg_profit),
                'best_profit_percentage': float(stats.best_profit),
                'most_profitable_dexs': stats.most_profitable_dexs,
                'last_opportunity': stats.last_opportunity.isoformat() if stats.last_opportunity else None
            })

        return result

    async def test_opportunity_detection(self) -> Dict:
        """Test opportunity detection system and return diagnostics."""
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'scanner_status': 'operational',
            'tests': {}
        }

        try:
            # Test 1: Basic scanning functionality
            logger.info("Testing opportunity detection...")
            test_opportunities = await self.scan_for_opportunities()
            test_results['tests']['basic_scan'] = {
                'status': 'passed',
                'opportunities_found': len(test_opportunities)
            }

            # Test 2: Price feed connectivity
            health_status = await self.price_feeds.get_health_status()
            test_results['tests']['price_feeds'] = {
                'status': 'passed' if health_status.get('status') == 'healthy' else 'warning',
                'details': health_status
            }

            # Test 3: Filtering and ranking
            if test_opportunities:
                filtered_ops = await self._filter_opportunities(test_opportunities)
                ranked_ops = self._rank_opportunities(filtered_ops)
                test_results['tests']['filtering_ranking'] = {
                    'status': 'passed',
                    'original_count': len(test_opportunities),
                    'filtered_count': len(filtered_ops),
                    'top_opportunity_profit': float(ranked_ops[0].profit_percentage) if ranked_ops else 0
                }
            else:
                test_results['tests']['filtering_ranking'] = {
                    'status': 'skipped',
                    'reason': 'no_opportunities_found'
                }

            # Test 4: Metrics collection
            current_metrics = self.get_scanner_metrics()
            test_results['tests']['metrics'] = {
                'status': 'passed',
                'total_scans': current_metrics['total_scans'],
                'opportunities_found': current_metrics['opportunities_found']
            }

            logger.info("Opportunity detection test completed successfully")

        except Exception as e:
            logger.error(f"Opportunity detection test failed: {e}")
            test_results['scanner_status'] = 'error'
            test_results['error'] = str(e)

        return test_results

    def export_analytics(self, filepath: str = None) -> Dict:
        """Export comprehensive analytics data."""
        analytics_data = {
            'export_timestamp': datetime.now().isoformat(),
            'scanner_metrics': self.get_scanner_metrics(),
            'token_pair_analytics': self.get_token_pair_analytics(),
            'recent_opportunities': self.get_recent_opportunities(50),
            'top_performing_pairs': self.get_top_performing_pairs(20),
            'configuration': {
                'scan_interval': self.scan_interval,
                'min_profit_threshold': self.min_profit_threshold,
                'max_opportunities_per_scan': self.max_opportunities_per_scan,
                'adaptive_scanning': self.adaptive_scanning,
                'monitored_pairs_count': len(self.monitored_pairs),
                'trade_amounts_count': len(self.trade_amounts)
            }
        }

        # Save to file if filepath provided
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(analytics_data, f, indent=2, default=str)
                logger.info(f"Analytics exported to {filepath}")
            except Exception as e:
                logger.error(f"Failed to export analytics to {filepath}: {e}")

        return analytics_data

    def __str__(self) -> str:
        """String representation of OpportunityScanner."""
        return (f"OpportunityScanner(pairs={len(self.monitored_pairs)}, "
                f"scans={self.metrics.total_scans}, "
                f"found={self.metrics.opportunities_found})")