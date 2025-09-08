# bot/risk_manager.py
"""
Comprehensive Risk Management System for Flashloan Arbitrage Bot (CORRECTED)
Provides safety checks, position limits, and emergency controls with proper Polygon calculations
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime, timedelta

from web3 import Web3
from web3.exceptions import Web3Exception
from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware

from bot.utils.logger import get_logger
from config.settings import Settings

logger = get_logger(__name__)


@dataclass
class RiskMetrics:
    """Risk assessment metrics for trade evaluation"""
    profit_threshold_usd: Decimal
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
    Advanced Risk Management System with corrected Polygon calculations

    Features:
    - Pre-trade validation with multiple safety checks
    - Position sizing and exposure limits
    - Circuit breakers for consecutive failures
    - Network condition monitoring with POA support
    - Emergency pause functionality
    - Dynamic risk adjustment based on market conditions
    """

    def __init__(self, settings: Settings, web3: Web3):
        self.settings = settings
        self.web3 = web3

        # Add POA middleware for Polygon
        if not any(isinstance(middleware, type(ExtraDataToPOAMiddleware))
                   for middleware in self.web3.middleware_onion):
            self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # Risk Configuration - CORRECTED FOR REALISTIC TRADING
        self.max_position_size_usd = Decimal("10000")  # $10k max position
        self.daily_volume_limit_usd = Decimal("100000")  # $100k daily limit
        self.max_consecutive_failures = 5
        self.min_profit_threshold_usd = Decimal("0.50")  # $0.50 minimum profit
        self.max_slippage_tolerance = Decimal("0.03")  # 3% max slippage
        self.gas_cost_max_ratio = Decimal("0.5")  # Gas can't exceed 50% of profit

        # State Tracking
        self.consecutive_failures = 0
        self.daily_volume_usd = Decimal("0")
        self.last_reset_date = datetime.now().date()
        self.emergency_pause = False
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None

        # Performance Tracking
        self.trade_history: List[Dict] = []
        self.risk_assessments: List[TradeRisk] = []
        self.network_health_score = 1.0

        # Rate Limiting
        self.last_trade_time = 0
        self.min_trade_interval = 30  # 30 seconds between trades

        logger.info("🛡️ Risk Manager initialized with corrected Polygon calculations")
        self._log_risk_parameters()

    def _log_risk_parameters(self):
        """Log current risk management parameters"""
        params = {
            "max_position_size": f"${self.max_position_size_usd}",
            "daily_volume_limit": f"${self.daily_volume_limit_usd}",
            "min_profit_threshold": f"${self.min_profit_threshold_usd}",
            "max_slippage": f"{self.max_slippage_tolerance:.2%}",
            "max_gas_ratio": f"{self.gas_cost_max_ratio:.2%}",
            "max_failures": self.max_consecutive_failures
        }
        logger.info(f"🔧 Risk Parameters: {params}")

    async def assess_trade_risk(self, opportunity: Dict) -> TradeRisk:
        """
        Comprehensive trade risk assessment with corrected USD calculations

        Args:
            opportunity: Trading opportunity data

        Returns:
            TradeRisk: Complete risk assessment
        """
        try:
            warnings = []
            blockers = []
            risk_score = 0.0

            # Extract opportunity data - CORRECTED FOR USD VALUES
            token_in = opportunity.get('token_in', '')
            token_out = opportunity.get('token_out', '')
            amount_in_usd = Decimal(str(opportunity.get('amount_in', 0))) / Decimal(
                "1e6")  # Convert from USDC wei to USD
            expected_profit_usd = Decimal(str(opportunity.get('profit_usd', 0)))
            gas_cost_usd = Decimal(str(opportunity.get('gas_cost_usd', 0)))
            slippage = Decimal(str(opportunity.get('slippage', 0)))

            logger.info(
                f"🔍 Assessing risk for ${amount_in_usd:.2f} trade with ${expected_profit_usd:.2f} expected profit")

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

            # 3. Position Size Validation - CORRECTED
            if amount_in_usd > self.max_position_size_usd:
                blockers.append(f"Position size ${amount_in_usd:.2f} exceeds limit ${self.max_position_size_usd}")
                risk_score += 50
            elif amount_in_usd > self.max_position_size_usd * Decimal("0.8"):
                warnings.append("Position size near limit")
                risk_score += 15

            # 4. Daily Volume Check - CORRECTED
            self._reset_daily_limits_if_needed()
            if self.daily_volume_usd + amount_in_usd > self.daily_volume_limit_usd:
                remaining_capacity = self.daily_volume_limit_usd - self.daily_volume_usd
                if remaining_capacity <= 0:
                    blockers.append(
                        f"Daily volume limit exceeded (${self.daily_volume_usd:.2f}/${self.daily_volume_limit_usd})")
                    risk_score += 50
                else:
                    warnings.append(f"Limited daily capacity remaining: ${remaining_capacity:.2f}")
                    risk_score += 10
            elif self.daily_volume_usd + amount_in_usd > self.daily_volume_limit_usd * Decimal("0.8"):
                warnings.append("Approaching daily volume limit")
                risk_score += 10

            # 5. Profitability Analysis - CORRECTED
            if expected_profit_usd < self.min_profit_threshold_usd:
                blockers.append(f"Profit ${expected_profit_usd:.2f} below threshold ${self.min_profit_threshold_usd}")
                risk_score += 30
            elif expected_profit_usd < self.min_profit_threshold_usd * Decimal("1.5"):
                warnings.append("Profit margin is low")
                risk_score += 10

            # 6. Slippage Validation
            if slippage > self.max_slippage_tolerance:
                blockers.append(f"Slippage {slippage:.2%} exceeds tolerance {self.max_slippage_tolerance:.2%}")
                risk_score += 40
            elif slippage > self.max_slippage_tolerance * Decimal("0.7"):
                warnings.append("High slippage detected")
                risk_score += 15

            # 7. Gas Cost Analysis - CORRECTED
            if expected_profit_usd > 0:
                gas_ratio = gas_cost_usd / expected_profit_usd
            else:
                gas_ratio = Decimal("999")

            if gas_ratio > self.gas_cost_max_ratio:
                blockers.append(
                    f"Gas cost ratio {gas_ratio:.2%} too high (${gas_cost_usd:.3f} gas vs ${expected_profit_usd:.2f} profit)")
                risk_score += 35
            elif gas_ratio > self.gas_cost_max_ratio * Decimal("0.7"):
                warnings.append("Gas cost is significant portion of profit")
                risk_score += 12

            # 8. Network Health Check - FIXED FOR POLYGON POA
            network_score = await self._assess_network_health()
            if network_score < 0.6:
                warnings.append(f"Network health degraded: {network_score:.2f}")
                risk_score += 10
            elif network_score < 0.8:
                warnings.append(f"Network health fair: {network_score:.2f}")
                risk_score += 5

            # 9. Token Pair Validation
            if not await self._validate_token_pair(token_in, token_out):
                blockers.append("Invalid or unsupported token pair")
                risk_score += 50

            # 10. Liquidity Assessment - SIMPLIFIED FOR TESTING
            liquidity_score = await self._assess_liquidity(token_in, token_out, amount_in_usd)
            if liquidity_score < 0.3:
                blockers.append(f"Insufficient liquidity: {liquidity_score:.2f}")
                risk_score += 30
            elif liquidity_score < 0.5:
                warnings.append(f"Limited liquidity: {liquidity_score:.2f}")
                risk_score += 10

            # Calculate final risk metrics
            metrics = RiskMetrics(
                profit_threshold_usd=expected_profit_usd,
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
                    profit_threshold_usd=Decimal("0"),
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
        logger.info(f"📊 Metrics - Profit: ${m.profit_threshold_usd:.2f}, "
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
                    amount_usd = Decimal(str(opportunity.get('amount_in', 0))) / Decimal("1e6")
                    self.daily_volume_usd += amount_usd
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
            self.daily_volume_usd = Decimal("0")
            self.last_reset_date = current_date
            logger.info("🔄 Daily limits reset")

    async def _assess_network_health(self) -> float:
        """Assess network health with proper POA support for Polygon"""
        try:
            # Check latest block
            latest_block = self.web3.eth.get_block('latest')
            current_time = time.time()
            block_age = current_time - latest_block.timestamp

            # Network health factors
            health_score = 1.0

            # Block freshness (blocks should be recent)
            if block_age > 30:  # More than 30 seconds old
                health_score -= 0.2
            elif block_age > 15:
                health_score -= 0.1

            # Gas price analysis (very high gas = network congestion)
            try:
                gas_price = self.web3.eth.gas_price
                gas_price_gwei = gas_price / 1e9

                if gas_price_gwei > 200:  # > 200 gwei (very high for Polygon)
                    health_score -= 0.3
                elif gas_price_gwei > 100:  # > 100 gwei
                    health_score -= 0.15

                logger.debug(f"Network: Block age {block_age:.1f}s, Gas {gas_price_gwei:.1f} gwei")

            except Exception as e:
                logger.debug(f"Gas price check failed: {e}")
                health_score -= 0.1

            self.network_health_score = max(0.5, health_score)  # Minimum 0.5 for Polygon POA
            return self.network_health_score

        except Exception as e:
            logger.debug(f"Network health check failed: {e}")
            return 0.8  # Default good score for Polygon

    async def _validate_token_pair(self, token_in: str, token_out: str) -> bool:
        """Validate token pair is supported and safe"""
        try:
            # Basic validation
            if not token_in or not token_out:
                return False

            # Check if tokens are valid addresses
            if not Web3.is_address(token_in) or not Web3.is_address(token_out):
                return False

            # Major Polygon tokens - EXPANDED LIST
            major_tokens = [
                '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',  # USDC
                '0xc2132d05d31c914a87c6611c10748aeb04b58e8f',  # USDT
                '0x8f3cf7ad23cd3cadbd9735aff958023239c6a063',  # DAI
                '0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270',  # WMATIC
                '0x7ceb23fd6bc0add59e62ac25578270cff1b9f619',  # WETH
                '0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6',  # WBTC
                '0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39',  # LINK
                '0xd6df932a45c0f255f85145f286ea0b292b21c90b',  # AAVE
            ]

            # Convert to lowercase for comparison
            token_in_lower = token_in.lower()
            token_out_lower = token_out.lower()

            # Both tokens must be in our supported list
            if (token_in_lower in major_tokens and token_out_lower in major_tokens):
                logger.debug(f"✅ Token pair validated: {token_in[:8]}.../{token_out[:8]}...")
                return True

            logger.debug(f"❌ Unsupported token pair: {token_in[:8]}.../{token_out[:8]}...")
            return False

        except Exception as e:
            logger.warning(f"⚠️ Token validation failed: {e}")
            return False

    async def _assess_liquidity(self, token_in: str, token_out: str, amount_usd: Decimal) -> float:
        """Assess liquidity for token pair and amount"""
        try:
            # Simplified liquidity assessment for major pairs
            major_tokens = [
                '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',  # USDC
                '0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270',  # WMATIC
                '0x7ceb23fd6bc0add59e62ac25578270cff1b9f619',  # WETH
            ]

            if (token_in.lower() in major_tokens and token_out.lower() in major_tokens):
                if amount_usd < Decimal("1000"):  # < $1k
                    return 0.9
                elif amount_usd < Decimal("5000"):  # < $5k
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
            'daily_volume_usd': str(self.daily_volume_usd),
            'daily_volume_limit_usd': str(self.daily_volume_limit_usd),
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
            'daily_volume_used_usd': str(self.daily_volume_usd),
            'daily_volume_remaining_usd': str(self.daily_volume_limit_usd - self.daily_volume_usd)
        }