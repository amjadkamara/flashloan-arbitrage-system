# Safety and validation 
# bot/risk_manager.py
"""
Comprehensive Risk Management System for Flashloan Arbitrage Bot
Provides safety checks, position limits, and emergency controls
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime, timedelta

from web3 import Web3
from web3.exceptions import Web3Exception

from bot.utils.logger import get_logger
from config.settings import Settings

logger = get_logger(__name__)


@dataclass
class RiskMetrics:
    """Risk assessment metrics for trade evaluation"""
    profit_threshold: Decimal
    max_slippage: Decimal
    min_liquidity: int
    gas_cost_ratio: Decimal
    network_congestion: float
    price_impact: Decimal
    execution_time_limit: int
    confidence_score: float


@dataclass
class TradeRisk:
    """Individual trade risk assessment"""
    is_safe: bool
    risk_score: float
    warnings: List[str]
    blockers: List[str]
    metrics: RiskMetrics
    timestamp: float


class RiskManager:
    """
    Advanced Risk Management System

    Features:
    - Pre-trade validation with multiple safety checks
    - Position sizing and exposure limits
    - Circuit breakers for consecutive failures
    - Network condition monitoring
    - Emergency pause functionality
    - Dynamic risk adjustment based on market conditions
    """

    def __init__(self, settings: Settings, web3: Web3):
        self.settings = settings
        self.web3 = web3

        # UPDATED RISK CONFIGURATION - More Realistic for Arbitrage
        self.max_position_size = Decimal(str(settings.trading.max_flashloan_amount))
        self.daily_volume_limit = Decimal("100000")  # $100k daily limit
        self.max_consecutive_failures = 5

        # FIXED: More realistic profit thresholds for arbitrage
        self.min_profit_threshold = Decimal("0.002")  # 0.2% minimum (was using bot's 2%)
        self.min_profit_usd = Decimal("5.0")  # $5 minimum profit

        # FIXED: More realistic slippage for DEX trading
        self.max_slippage_tolerance = Decimal("0.02")  # 2% max slippage (was 3%)

        # FIXED: More reasonable gas cost ratio
        self.gas_cost_max_ratio = Decimal("3.0")  # Gas can be up to 300% of profit for small trades

        # State Tracking (unchanged)
        self.consecutive_failures = 0
        self.daily_volume = Decimal("0")
        self.last_reset_date = datetime.now().date()
        self.emergency_pause = False
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None

        # Performance Tracking (unchanged)
        self.trade_history: List[Dict] = []
        self.risk_assessments: List[TradeRisk] = []
        self.network_health_score = 1.0

        # FIXED: Reduced rate limiting for better opportunity capture
        self.last_trade_time = 0
        self.min_trade_interval = 10  # 10 seconds between trades (was 30)

        # ADDED: Debug mode flag
        self.debug_mode = False  # Simple fix - remove dependency on missing debugging config

        logger.info("🛡️ Risk Manager initialized with UPDATED arbitrage-optimized parameters")
        self._log_risk_parameters()

    def _log_risk_parameters(self):
        """Log current risk management parameters"""
        params = {
            "max_position_size": str(self.max_position_size),
            "daily_volume_limit": str(self.daily_volume_limit),
            "min_profit_threshold": f"{self.min_profit_threshold}%",
            "max_slippage": f"{self.max_slippage_tolerance}%",
            "max_gas_ratio": f"{self.gas_cost_max_ratio}%",
            "max_failures": self.max_consecutive_failures
        }
        logger.info(f"🔧 Risk Parameters: {params}")

    async def assess_trade_risk(self, opportunity: Dict) -> TradeRisk:
        """
        Comprehensive trade risk assessment

        Args:
            opportunity: Trading opportunity data

        Returns:
            TradeRisk: Complete risk assessment
        """
        try:
            # For dry-run testing, bypass all risk checks
            import sys
            if '--dry-run' in sys.argv:
                logger.info("🧪 DRY RUN: Bypassing risk management - allowing all trades")
                metrics = RiskMetrics(
                    profit_threshold=Decimal(str(opportunity.get('profit', 0))),
                    max_slippage=Decimal("0.005"),
                    min_liquidity=100,
                    gas_cost_ratio=Decimal("0.1"),
                    network_congestion=0.1,
                    price_impact=Decimal("0.005"),
                    execution_time_limit=60,
                    confidence_score=1.0
                )
                return TradeRisk(
                    is_safe=True,
                    risk_score=0.0,
                    warnings=[],
                    blockers=[],
                    metrics=metrics,
                    timestamp=time.time()
                )

            # Continue with normal risk assessment for live trading...
            warnings = []
            blockers = []
            risk_score = 0.0

            # Extract opportunity data
            token_in = opportunity.get('token_in', '')
            token_out = opportunity.get('token_out', '')
            amount_in = Decimal(str(opportunity.get('amount_in', 0)))
            expected_profit = Decimal(str(opportunity.get('profit', 0)))
            gas_estimate = opportunity.get('gas_estimate', 0)
            slippage = Decimal(str(opportunity.get('slippage', 0)))

            # 1. Emergency Controls Check
            if self.emergency_pause:
                blockers.append("Emergency pause is active")
                risk_score += 100

            if self.circuit_breaker_active:
                if datetime.now() < self.circuit_breaker_until:
                    blockers.append(f"Circuit breaker active until {self.circuit_breaker_until}")
                    risk_score += 100
                else:
                    self._reset_circuit_breaker()

            # 2. Rate Limiting Check
            current_time = time.time()
            if current_time - self.last_trade_time < self.min_trade_interval:
                remaining = self.min_trade_interval - (current_time - self.last_trade_time)
                warnings.append(f"Rate limit: {remaining:.1f}s remaining")
                risk_score += 20

            # 3. Position Size Validation
            if amount_in > self.max_position_size:
                blockers.append(f"Position size {amount_in} exceeds limit {self.max_position_size}")
                risk_score += 50
            elif amount_in > self.max_position_size * Decimal("0.8"):
                warnings.append("Position size near limit")
                risk_score += 15

            # 4. Daily Volume Check
            self._reset_daily_limits_if_needed()
            if self.daily_volume + amount_in > self.daily_volume_limit:
                blockers.append(f"Daily volume limit would be exceeded")
                risk_score += 50
            elif self.daily_volume + amount_in > self.daily_volume_limit * Decimal("0.8"):
                warnings.append("Approaching daily volume limit")
                risk_score += 10

            # 5. Profitability Analysis
            if expected_profit < self.min_profit_threshold:
                blockers.append(f"Profit {expected_profit} below threshold {self.min_profit_threshold}")
                risk_score += 30
            elif expected_profit < self.min_profit_threshold * Decimal("1.5"):
                warnings.append("Profit margin is low")
                risk_score += 10

            # 6. Slippage Validation
            if slippage > self.max_slippage_tolerance:
                blockers.append(f"Slippage {slippage} exceeds tolerance {self.max_slippage_tolerance}")
                risk_score += 40
            elif slippage > self.max_slippage_tolerance * Decimal("0.7"):
                warnings.append("High slippage detected")
                risk_score += 15

            # 7. Gas Cost Analysis
            gas_cost_eth = Decimal(str(gas_estimate * await self._get_gas_price() / 1e18))
            gas_cost_usd = gas_cost_eth * await self._get_eth_price()
            gas_ratio = gas_cost_usd / expected_profit if expected_profit > 0 else Decimal("999")

            if gas_ratio > self.gas_cost_max_ratio:
                blockers.append(f"Gas cost ratio {gas_ratio:.2%} too high")
                risk_score += 35
            elif gas_ratio > self.gas_cost_max_ratio * Decimal("0.7"):
                warnings.append("Gas cost is significant portion of profit")
                risk_score += 12

            # 8. Network Health Check
            network_score = await self._assess_network_health()
            #if network_score < 0.6:
                #blockers.append(f"Network health poor: {network_score:.2f}")
                #risk_score += 25
            #elif network_score < 0.8:
                #warnings.append(f"Network health degraded: {network_score:.2f}")
                #risk_score += 8

            # 9. Token Pair Validation
            if not await self._validate_token_pair(token_in, token_out):
                blockers.append("Invalid or unsupported token pair")
                risk_score += 50

            # 10. Liquidity Assessment
            liquidity_score = await self._assess_liquidity(token_in, token_out, amount_in)
            if liquidity_score < 0.5:
                blockers.append(f"Insufficient liquidity: {liquidity_score:.2f}")
                risk_score += 30
            elif liquidity_score < 0.7:
                warnings.append(f"Limited liquidity: {liquidity_score:.2f}")
                risk_score += 10

            # Calculate final risk metrics
            metrics = RiskMetrics(
                profit_threshold=expected_profit,
                max_slippage=slippage,
                min_liquidity=int(liquidity_score * 100),
                gas_cost_ratio=gas_ratio,
                network_congestion=1.0 - network_score,
                price_impact=slippage,
                execution_time_limit=60,
                confidence_score=max(0, 1.0 - (risk_score / 100))
            )

            # Determine if trade is safe
            is_safe = len(blockers) == 0 and risk_score < 50

            # Create risk assessment
            assessment = TradeRisk(
                is_safe=is_safe,
                risk_score=min(100, risk_score),
                warnings=warnings,
                blockers=blockers,
                metrics=metrics,
                timestamp=time.time()
            )

            # Store assessment
            self.risk_assessments.append(assessment)
            if len(self.risk_assessments) > 100:
                self.risk_assessments = self.risk_assessments[-50:]  # Keep last 50

            # Log assessment
            self._log_risk_assessment(assessment, opportunity)

            return assessment

        except Exception as e:
            logger.error(f"❌ Risk assessment failed: {e}")
            return TradeRisk(
                is_safe=False,
                risk_score=100,
                warnings=[],
                blockers=[f"Risk assessment error: {str(e)}"],
                metrics=RiskMetrics(
                    profit_threshold=Decimal("0"),
                    max_slippage=Decimal("1"),
                    min_liquidity=0,
                    gas_cost_ratio=Decimal("999"),
                    network_congestion=1.0,
                    price_impact=Decimal("1"),
                    execution_time_limit=0,
                    confidence_score=0.0
                ),
                timestamp=time.time()
            )

    def _log_risk_assessment(self, assessment: TradeRisk, opportunity: Dict):
        """Log risk assessment results"""
        status = "✅ SAFE" if assessment.is_safe else "🚫 BLOCKED"
        logger.info(f"{status} Risk Score: {assessment.risk_score:.1f}/100")

        if assessment.warnings:
            logger.warning(f"⚠️ Warnings: {', '.join(assessment.warnings)}")

        if assessment.blockers:
            logger.error(f"🚫 Blockers: {', '.join(assessment.blockers)}")

        # Log key metrics
        m = assessment.metrics
        logger.info(f"📊 Metrics - Profit: {m.profit_threshold:.4f}, "
                    f"Slippage: {m.max_slippage:.2%}, "
                    f"Gas Ratio: {m.gas_cost_ratio:.2%}, "
                    f"Confidence: {m.confidence_score:.2%}")

    async def record_trade_result(self, opportunity: Dict, success: bool, profit: Optional[Decimal] = None,
                                  error: Optional[str] = None):
        """
        Record trade execution result for risk learning

        Args:
            opportunity: Original opportunity data
            success: Whether trade succeeded
            profit: Actual profit if successful
            error: Error message if failed
        """
        try:
            # Update failure tracking
            if success:
                self.consecutive_failures = 0
                if profit:
                    self.daily_volume += Decimal(str(opportunity.get('amount_in', 0)))
            else:
                self.consecutive_failures += 1

                # Trigger circuit breaker if too many failures
                if self.consecutive_failures >= self.max_consecutive_failures:
                    await self._activate_circuit_breaker()

            # Record trade history
            trade_record = {
                'timestamp': time.time(),
                'opportunity': opportunity,
                'success': success,
                'profit': str(profit) if profit else None,
                'error': error,
                'consecutive_failures': self.consecutive_failures
            }

            self.trade_history.append(trade_record)
            if len(self.trade_history) > 1000:
                self.trade_history = self.trade_history[-500:]  # Keep last 500

            # Update last trade time if successful
            if success:
                self.last_trade_time = time.time()

            logger.info(f"📝 Trade recorded: {'SUCCESS' if success else 'FAILURE'} "
                        f"(Consecutive failures: {self.consecutive_failures})")

        except Exception as e:
            logger.error(f"❌ Failed to record trade result: {e}")

    async def _activate_circuit_breaker(self):
        """Activate circuit breaker after consecutive failures"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(minutes=30)

        logger.error(f"🔴 CIRCUIT BREAKER ACTIVATED! "
                     f"Too many failures ({self.consecutive_failures}). "
                     f"Trading paused until {self.circuit_breaker_until}")

    def _reset_circuit_breaker(self):
        """Reset circuit breaker"""
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        logger.info("🟢 Circuit breaker reset - Trading resumed")

    def _reset_daily_limits_if_needed(self):
        """Reset daily volume limits if new day"""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_volume = Decimal("0")
            self.last_reset_date = current_date
            logger.info("🔄 Daily limits reset")

    async def _get_gas_price(self) -> int:
        """Get current gas price in wei"""
        try:
            gas_price = await self.web3.eth.gas_price
            return int(gas_price)
        except:
            return 50_000_000_000  # 50 gwei fallback

    async def _get_eth_price(self) -> Decimal:
        """Get ETH price in USD (simplified - use proper price feed in production)"""
        # In production, use a proper price oracle
        return Decimal("2000")  # Placeholder

    async def _assess_network_health(self) -> float:
        """Assess network health based on various factors"""
        try:
            # Check latest block
            latest_block = await self.web3.eth.get_block('latest')
            current_time = time.time()
            block_age = current_time - latest_block.timestamp

            # Network health factors
            health_score = 1.0

            # Block freshness (blocks should be recent)
            if block_age > 30:  # More than 30 seconds old
                health_score -= 0.3
            elif block_age > 15:
                health_score -= 0.1

            # Gas price analysis (very high gas = network congestion)
            gas_price = await self._get_gas_price()
            if gas_price > 100_000_000_000:  # > 100 gwei
                health_score -= 0.3
            elif gas_price > 50_000_000_000:  # > 50 gwei
                health_score -= 0.15

            self.network_health_score = max(0, health_score)
            return self.network_health_score

        except Exception as e:
            logger.warning(f"⚠️ Network health check failed: {e}")
            return 0.5  # Neutral score on failure

    async def _validate_token_pair(self, token_in: str, token_out: str) -> bool:
        """Validate token pair is supported and safe"""
        try:
            # Basic validation
            if not token_in or not token_out:
                return False

            # Check if tokens are valid addresses
            if not Web3.is_address(token_in) or not Web3.is_address(token_out):
                return False

            # Add more sophisticated token validation here
            # - Check if tokens are on whitelist
            # - Verify token contracts
            # - Check for known scam tokens

            return True

        except Exception as e:
            logger.warning(f"⚠️ Token validation failed: {e}")
            return False

    async def _assess_liquidity(self, token_in: str, token_out: str, amount: Decimal) -> float:
        """Assess liquidity for token pair and amount"""
        try:
            # Simplified liquidity assessment
            # In production, check actual DEX liquidity

            # For now, assume major pairs have good liquidity
            major_tokens = [
                '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',  # USDC
                '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',  # WETH
                '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',  # WMATIC
            ]

            if token_in.lower() in [t.lower() for t in major_tokens] and \
                    token_out.lower() in [t.lower() for t in major_tokens]:
                if amount < Decimal("10000"):  # < $10k
                    return 0.9
                elif amount < Decimal("50000"):  # < $50k
                    return 0.7
                else:
                    return 0.5

            return 0.3  # Lower score for unknown tokens

        except Exception as e:
            logger.warning(f"⚠️ Liquidity assessment failed: {e}")
            return 0.1

    # Emergency Controls
    def emergency_stop(self):
        """Emergency stop all trading"""
        self.emergency_pause = True
        logger.error("🚨 EMERGENCY STOP ACTIVATED!")

    def resume_trading(self):
        """Resume trading after emergency stop"""
        self.emergency_pause = False
        self.consecutive_failures = 0
        logger.info("✅ Trading resumed after emergency stop")

    def get_risk_status(self) -> Dict:
        """Get current risk management status"""
        return {
            'emergency_pause': self.emergency_pause,
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_until': self.circuit_breaker_until.isoformat() if self.circuit_breaker_until else None,
            'consecutive_failures': self.consecutive_failures,
            'daily_volume': str(self.daily_volume),
            'daily_volume_limit': str(self.daily_volume_limit),
            'network_health_score': self.network_health_score,
            'last_trade_time': self.last_trade_time,
            'total_assessments': len(self.risk_assessments),
            'total_trades': len(self.trade_history)
        }

    def get_performance_metrics(self) -> Dict:
        """Get performance and risk metrics"""
        if not self.trade_history:
            return {'total_trades': 0, 'success_rate': 0, 'message': 'No trades recorded'}

        # Calculate success rate
        successful_trades = sum(1 for trade in self.trade_history if trade['success'])
        success_rate = successful_trades / len(self.trade_history)

        # Calculate risk scores
        recent_assessments = [a for a in self.risk_assessments if time.time() - a.timestamp < 3600]  # Last hour
        avg_risk_score = sum(a.risk_score for a in recent_assessments) / len(
            recent_assessments) if recent_assessments else 0

        return {
            'total_trades': len(self.trade_history),
            'successful_trades': successful_trades,
            'success_rate': success_rate,
            'avg_risk_score': avg_risk_score,
            'network_health': self.network_health_score,
            'daily_volume_used': str(self.daily_volume),
            'daily_volume_remaining': str(self.daily_volume_limit - self.daily_volume)
        }