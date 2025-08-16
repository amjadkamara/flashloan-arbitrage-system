# Main bot orchestration 
# bot/arbitrage_bot.py
"""
Main Flashloan Arbitrage Bot - Updated Integration
Orchestrates all components: scanning, risk management, and execution
"""

import asyncio
import time
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from web3 import Web3
from web3.exceptions import Web3Exception

from bot.opportunity_scanner import OpportunityScanner
from bot.risk_manager import RiskManager
from bot.contract_interface import ContractInterface
from bot.price_feeds import PriceFeeds
from bot.utils.logger import get_logger
from bot.utils.notifications import NotificationManager
from config.settings import Settings

logger = get_logger(__name__)


class FlashloanArbitrageBot:
    """
    Main Flashloan Arbitrage Bot

    Features:
    - Continuous opportunity scanning
    - Comprehensive risk management
    - Automated trade execution
    - Performance monitoring
    - Emergency controls
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.running = False
        self.paused = False

        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(settings.RPC_URL))
        if not self.web3.is_connected():
            raise ConnectionError("❌ Failed to connect to Polygon network")

        logger.info(f"🌐 Connected to Polygon - Chain ID: {self.web3.eth.chain_id}")

        # Initialize components
        self.price_feeds = PriceFeeds(settings)
        self.contract_interface = ContractInterface(settings, self.web3)
        self.risk_manager = RiskManager(settings, self.web3)
        self.opportunity_scanner = OpportunityScanner(settings, self.price_feeds)
        self.notification_manager = NotificationManager(settings)

        # Performance tracking
        self.start_time = None
        self.total_opportunities_found = 0
        self.total_trades_attempted = 0
        self.total_successful_trades = 0
        self.total_profit = Decimal("0")

        logger.info("🤖 Flashloan Arbitrage Bot initialized successfully")
        self._log_configuration()

    def _log_configuration(self):
        """Log bot configuration"""
        config = {
            'network': 'Polygon',
            'min_profit_threshold': f"{self.settings.MIN_PROFIT_THRESHOLD}%",
            'max_position_size': f"${self.settings.MAX_FLASHLOAN_AMOUNT:,.2f}",
            'scan_interval': f"{self.settings.SCAN_INTERVAL}s",
            'risk_management': 'Enabled'
        }
        logger.info(f"⚙️ Bot Configuration: {config}")

    async def start(self):
        """Start the arbitrage bot"""
        if self.running:
            logger.warning("⚠️ Bot is already running")
            return

        self.running = True
        self.start_time = time.time()

        logger.info("🚀 Starting Flashloan Arbitrage Bot...")
        await self.notification_manager.send_notification(
            "🚀 Arbitrage Bot Started",
            "Bot is now scanning for opportunities"
        )

        try:
            # Initialize all components
            await self.price_feeds.start()
            await self.contract_interface.initialize()

            # Start main trading loop
            await self._main_trading_loop()

        except Exception as e:
            logger.error(f"❌ Bot startup failed: {e}")
            await self.notification_manager.send_notification(
                "❌ Bot Startup Failed",
                f"Error: {str(e)}"
            )
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the arbitrage bot"""
        if not self.running:
            return

        self.running = False
        logger.info("🛑 Stopping Flashloan Arbitrage Bot...")

        # Stop components
        if hasattr(self.price_feeds, 'stop'):
            await self.price_feeds.stop()

        # Send final report
        await self._send_session_report()

        logger.info("✅ Bot stopped successfully")

    async def pause(self):
        """Pause bot operations"""
        self.paused = True
        logger.info("⏸️ Bot paused")
        await self.notification_manager.send_notification(
            "⏸️ Bot Paused",
            "Bot operations temporarily paused"
        )

    async def resume(self):
        """Resume bot operations"""
        self.paused = False
        logger.info("▶️ Bot resumed")
        await self.notification_manager.send_notification(
            "▶️ Bot Resumed",
            "Bot operations resumed"
        )

    async def emergency_stop(self):
        """Emergency stop with risk manager integration"""
        logger.error("🚨 EMERGENCY STOP TRIGGERED!")

        # Stop risk manager
        self.risk_manager.emergency_stop()

        # Stop bot
        await self.stop()

        await self.notification_manager.send_notification(
            "🚨 EMERGENCY STOP",
            "Bot stopped due to emergency condition"
        )

    async def _main_trading_loop(self):
        """Main trading loop - scan and execute opportunities"""
        logger.info("🔄 Starting main trading loop...")

        while self.running:
            try:
                if self.paused:
                    await asyncio.sleep(5)
                    continue

                # Check risk manager status
                risk_status = self.risk_manager.get_risk_status()
                if risk_status['emergency_pause'] or risk_status['circuit_breaker_active']:
                    logger.info("⏸️ Trading paused due to risk management")
                    await asyncio.sleep(30)
                    continue

                # Scan for opportunities
                opportunities = await self.opportunity_scanner.scan_for_opportunities()
                self.total_opportunities_found += len(opportunities)

                if not opportunities:
                    await asyncio.sleep(self.settings.SCAN_INTERVAL)
                    continue

                logger.info(f"🔍 Found {len(opportunities)} opportunities")

                # Process each opportunity
                for opportunity in opportunities:
                    if not self.running or self.paused:
                        break

                    await self._process_opportunity(opportunity)

                # Wait before next scan
                await asyncio.sleep(self.settings.SCAN_INTERVAL)

            except KeyboardInterrupt:
                logger.info("⌨️ Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def _process_opportunity(self, opportunity: Dict):
        """Process a single arbitrage opportunity"""
        try:
            logger.info(f"📊 Processing opportunity: {opportunity.get('pair', 'Unknown')}")

            # Step 1: Risk Assessment
            risk_assessment = await self.risk_manager.assess_trade_risk(opportunity)

            if not risk_assessment.is_safe:
                logger.warning(f"🚫 Opportunity rejected due to risk: {risk_assessment.blockers}")
                return

            if risk_assessment.warnings:
                logger.warning(f"⚠️ Proceeding with warnings: {risk_assessment.warnings}")

            # Step 2: Prepare Trade Parameters
            trade_params = await self._prepare_trade_parameters(opportunity, risk_assessment)
            if not trade_params:
                logger.error("❌ Failed to prepare trade parameters")
                return

            # Step 3: Execute Trade
            logger.info(f"⚡ Executing arbitrage trade...")
            self.total_trades_attempted += 1

            success, result = await self._execute_arbitrage_trade(trade_params)

            # Step 4: Record Results
            await self._record_trade_result(opportunity, success, result)

        except Exception as e:
            logger.error(f"❌ Error processing opportunity: {e}")
            await self.risk_manager.record_trade_result(
                opportunity,
                False,
                error=str(e)
            )

    async def _prepare_trade_parameters(self, opportunity: Dict, risk_assessment) -> Optional[Dict]:
        """Prepare parameters for trade execution"""
        try:
            # Extract opportunity data
            token_in = opportunity.get('token_in')
            token_out = opportunity.get('token_out')
            amount_in = int(float(opportunity.get('amount_in', 0)))

            # Get optimal swap routes
            route_data = await self.price_feeds.get_swap_route(
                token_in, token_out, amount_in
            )

            if not route_data:
                logger.error("❌ Failed to get swap route")
                return None

            # Prepare trade parameters
            trade_params = {
                'flashloan_asset': token_in,
                'flashloan_amount': amount_in,
                'dex_buy': route_data.get('dex_buy'),
                'dex_sell': route_data.get('dex_sell'),
                'buy_calldata': route_data.get('buy_calldata'),
                'sell_calldata': route_data.get('sell_calldata'),
                'min_profit': int(float(risk_assessment.metrics.profit_threshold) * 1e6),  # Convert to wei
                'gas_limit': route_data.get('gas_estimate', 500000),
                'deadline': int(time.time() + 300)  # 5 minute deadline
            }

            return trade_params

        except Exception as e:
            logger.error(f"❌ Failed to prepare trade parameters: {e}")
            return None

    async def _execute_arbitrage_trade(self, trade_params: Dict) -> tuple[bool, Optional[Dict]]:
        """Execute the arbitrage trade via smart contract"""
        try:
            # Execute trade through contract interface
            tx_hash = await self.contract_interface.execute_arbitrage(trade_params)

            if not tx_hash:
                logger.error("❌ Trade execution failed - no transaction hash")
                return False, None

            logger.info(f"📝 Trade submitted: {tx_hash}")

            # Wait for transaction confirmation
            receipt = await self.contract_interface.wait_for_confirmation(tx_hash)

            if receipt and receipt.status == 1:
                # Parse transaction results
                result = await self._parse_trade_result(receipt)
                logger.info(f"✅ Trade successful! Profit: ${result.get('profit', 0):.2f}")

                # Send success notification
                await self.notification_manager.send_notification(
                    "✅ Arbitrage Success!",
                    f"Profit: ${result.get('profit', 0):.2f}\nTx: {tx_hash}"
                )

                return True, result
            else:
                logger.error(f"❌ Trade failed - transaction reverted: {tx_hash}")
                return False, None

        except Exception as e:
            logger.error(f"❌ Trade execution error: {e}")
            return False, None

    async def _parse_trade_result(self, receipt) -> Dict:
        """Parse trade results from transaction receipt"""
        try:
            # Parse logs to extract profit information
            # This is simplified - in production, parse actual contract events

            gas_used = receipt.gasUsed
            gas_price = receipt.effectiveGasPrice
            gas_cost = gas_used * gas_price / 1e18  # Convert to ETH
            gas_cost_usd = gas_cost * 2000  # Approximate ETH price

            # For now, return basic information
            # In production, parse actual profit from contract events
            return {
                'gas_used': gas_used,
                'gas_cost_usd': gas_cost_usd,
                'profit': 0.0,  # Parse from contract events
                'tx_hash': receipt.transactionHash.hex()
            }

        except Exception as e:
            logger.error(f"❌ Failed to parse trade result: {e}")
            return {'profit': 0.0, 'error': str(e)}

    async def _record_trade_result(self, opportunity: Dict, success: bool, result: Optional[Dict]):
        """Record trade result for tracking and risk management"""
        try:
            profit = None
            error = None

            if success and result:
                profit = Decimal(str(result.get('profit', 0)))
                self.total_successful_trades += 1
                self.total_profit += profit
            elif result and 'error' in result:
                error = result['error']

            # Record with risk manager
            await self.risk_manager.record_trade_result(
                opportunity, success, profit, error
            )

            # Log performance update
            self._log_performance_update()

        except Exception as e:
            logger.error(f"❌ Failed to record trade result: {e}")

    def _log_performance_update(self):
        """Log current performance metrics"""
        if self.start_time:
            runtime = time.time() - self.start_time
            runtime_hours = runtime / 3600

            success_rate = (self.total_successful_trades / self.total_trades_attempted * 100
                            if self.total_trades_attempted > 0 else 0)

            logger.info(f"📈 Performance Update:")
            logger.info(f"   Runtime: {runtime_hours:.1f}h")
            logger.info(f"   Opportunities: {self.total_opportunities_found}")
            logger.info(f"   Trades Attempted: {self.total_trades_attempted}")
            logger.info(f"   Success Rate: {success_rate:.1f}%")
            logger.info(f"   Total Profit: ${self.total_profit:.2f}")

    async def _send_session_report(self):
        """Send final session report"""
        try:
            if not self.start_time:
                return

            runtime = time.time() - self.start_time
            runtime_hours = runtime / 3600

            success_rate = (self.total_successful_trades / self.total_trades_attempted * 100
                            if self.total_trades_attempted > 0 else 0)

            # Get risk manager metrics
            risk_metrics = self.risk_manager.get_performance_metrics()

            report = f"""
📊 **Trading Session Report**

⏱️ **Session Duration:** {runtime_hours:.1f} hours
🔍 **Opportunities Found:** {self.total_opportunities_found}
⚡ **Trades Attempted:** {self.total_trades_attempted}
✅ **Successful Trades:** {self.total_successful_trades}
📈 **Success Rate:** {success_rate:.1f}%
💰 **Total Profit:** ${self.total_profit:.2f}
🛡️ **Risk Score:** {risk_metrics.get('avg_risk_score', 0):.1f}/100
🌐 **Network Health:** {risk_metrics.get('network_health', 0):.1%}
"""

            await self.notification_manager.send_notification(
                "📊 Session Report", report
            )

        except Exception as e:
            logger.error(f"❌ Failed to send session report: {e}")

    # Status and Control Methods
    def get_status(self) -> Dict:
        """Get current bot status"""
        runtime = time.time() - self.start_time if self.start_time else 0

        return {
            'running': self.running,
            'paused': self.paused,
            'runtime_seconds': runtime,
            'opportunities_found': self.total_opportunities_found,
            'trades_attempted': self.total_trades_attempted,
            'successful_trades': self.total_successful_trades,
            'total_profit': str(self.total_profit),
            'risk_status': self.risk_manager.get_risk_status(),
            'scanner_status': self.opportunity_scanner.get_status(),
            'network_connected': self.web3.is_connected()
        }

    async def get_detailed_metrics(self) -> Dict:
        """Get detailed performance metrics"""
        status = self.get_status()
        risk_metrics = self.risk_manager.get_performance_metrics()
        scanner_metrics = self.opportunity_scanner.get_performance_metrics()

        return {
            **status,
            'risk_metrics': risk_metrics,
            'scanner_metrics': scanner_metrics,
            'price_feed_status': await self.price_feeds.get_status()
        }

    # Manual Control Methods
    async def force_scan(self) -> List[Dict]:
        """Force a manual opportunity scan"""
        logger.info("🔍 Forcing manual opportunity scan...")
        return await self.opportunity_scanner.scan_for_opportunities()

    async def test_opportunity(self, opportunity: Dict) -> Dict:
        """Test an opportunity without executing"""
        logger.info(f"🧪 Testing opportunity: {opportunity.get('pair', 'Unknown')}")

        risk_assessment = await self.risk_manager.assess_trade_risk(opportunity)
        trade_params = await self._prepare_trade_parameters(opportunity, risk_assessment)

        return {
            'opportunity': opportunity,
            'risk_assessment': {
                'is_safe': risk_assessment.is_safe,
                'risk_score': risk_assessment.risk_score,
                'warnings': risk_assessment.warnings,
                'blockers': risk_assessment.blockers
            },
            'trade_params': trade_params,
            'would_execute': risk_assessment.is_safe and trade_params is not None
        }


# Async Context Manager Support
class FlashloanArbitrageBotManager:
    """Async context manager for the bot"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bot = None

    async def __aenter__(self):
        self.bot = FlashloanArbitrageBot(self.settings)
        return self.bot

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.bot:
            await self.bot.stop()


# Main execution function
async def main():
    """Main execution function for testing"""
    from config.settings import Settings

    settings = Settings()

    async with FlashloanArbitrageBotManager(settings) as bot:
        try:
            await bot.start()
        except KeyboardInterrupt:
            logger.info("⌨️ Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")


if __name__ == "__main__":
    asyncio.run(main())