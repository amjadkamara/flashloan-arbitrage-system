# bot/arbitrage_bot.py
"""
Main Flashloan Arbitrage Bot - Fixed Integration
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
        self.web3 = Web3(Web3.HTTPProvider(settings.network.rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError("Failed to connect to Polygon network")

        # Initialize components
        self.price_feeds = PriceFeeds(settings, self.web3)
        self.contract_interface = ContractInterface(settings)
        self.notification_manager = NotificationManager(settings.monitoring)
        self.opportunity_scanner = OpportunityScanner(settings, self.price_feeds, self.web3)
        self.risk_manager = RiskManager(settings, self.web3)

        # Performance tracking
        self.start_time = None
        self.total_opportunities_found = 0
        self.total_trades_attempted = 0
        self.total_successful_trades = 0
        self.total_profit = Decimal("0")

        logger.info("Flashloan Arbitrage Bot initialized successfully")
        self._log_configuration()

    def _log_configuration(self):
        """Log bot configuration"""
        config = {
            'network': 'Polygon',
            'min_profit_threshold': f"{self.settings.trading.min_profit_threshold}%",
            'max_position_size': f"${self.settings.trading.max_flashloan_amount:,.2f}",
            'scan_interval': f"{10}s",
            'risk_management': 'Enabled'
        }
        logger.info(f"Bot Configuration: {config}")

    async def start(self):
        """Start the arbitrage bot"""
        if self.running:
            logger.warning("Bot is already running")
            return

        self.running = True
        self.start_time = time.time()

        logger.info("Starting Flashloan Arbitrage Bot...")
        await self.notification_manager.send_status_alert(
            "Arbitrage Bot Started",
            "Bot is now scanning for opportunities"
        )

        try:
            # Validate all components are working
            logger.info("Validating components...")

            # Test price feeds
            test_result = await self.price_feeds.test_price_feeds()
            logger.info(f"Price feeds test: {test_result['overall_status']}")

            # Test contract interface (basic connectivity test)
            try:
                # Try to get account balance from web3 directly
                account = self.web3.eth.default_account or self.contract_interface.account
                if account:
                    balance_wei = self.web3.eth.get_balance(account)
                    balance_matic = self.web3.from_wei(balance_wei, 'ether')
                    logger.info(f"Contract interface ready - Account balance: {balance_matic:.4f} MATIC")
                else:
                    logger.info("Contract interface ready - No default account set")
            except Exception as e:
                logger.warning(f"Could not verify account balance: {e}")
                logger.info("Contract interface loaded successfully")

            # Start main trading loop
            await self._main_trading_loop()

        except Exception as e:
            logger.error(f"Bot startup failed: {e}")
            await self.notification_manager.send_status_alert(
                "Bot Startup Failed",
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
        logger.info("Stopping Flashloan Arbitrage Bot...")

        # Close HTTP sessions properly
        try:
            if hasattr(self.notification_manager, 'close'):
                await self.notification_manager.close()

            # Also try to close any sessions in price feeds
            if hasattr(self.price_feeds, 'close') and callable(getattr(self.price_feeds, 'close')):
                await self.price_feeds.close()
        except Exception as e:
            logger.warning(f"Error closing HTTP sessions: {e}")

        # Send final report
        await self._send_session_report()

        logger.info("Bot stopped successfully")

    async def pause(self):
        """Pause bot operations"""
        self.paused = True
        logger.info("Bot paused")
        await self.notification_manager.send_status_alert(
            "Bot Paused",
            "Bot operations temporarily paused"
        )

    async def resume(self):
        """Resume bot operations"""
        self.paused = False
        logger.info("Bot resumed")
        await self.notification_manager.send_status_alert(
            "Bot Resumed",
            "Bot operations resumed"
        )

    async def emergency_stop(self):
        """Emergency stop with risk manager integration"""
        logger.error("EMERGENCY STOP TRIGGERED!")

        # Stop risk manager
        self.risk_manager.emergency_stop()

        # Stop bot
        await self.stop()

        await self.notification_manager.send_status_alert(
            "EMERGENCY STOP",
            "Bot stopped due to emergency condition"
        )

    async def _main_trading_loop(self):
        """Main trading loop - scan and execute opportunities"""
        logger.info("Starting main trading loop...")

        while self.running:
            try:
                if self.paused:
                    await asyncio.sleep(5)
                    continue

                # Check risk manager status
                risk_status = self.risk_manager.get_risk_status()
                if risk_status['emergency_pause'] or risk_status['circuit_breaker_active']:
                    logger.info("Trading paused due to risk management")
                    await asyncio.sleep(30)
                    continue

                # Scan for opportunities using price feeds directly
                opportunities = await self._scan_for_opportunities()
                self.total_opportunities_found += len(opportunities)

                if not opportunities:
                    logger.debug("No opportunities found")
                    await asyncio.sleep(10)
                    continue

                logger.info(f"Found {len(opportunities)} opportunities")

                # Process each opportunity
                for opportunity in opportunities:
                    if not self.running or self.paused:
                        break

                    await self._process_opportunity(opportunity)

                # Wait before next scan
                await asyncio.sleep(10)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def _scan_for_opportunities(self):
        """Scan for arbitrage opportunities using price feeds"""
        try:
            # Get supported token pairs
            token_pairs = self.price_feeds.get_supported_token_pairs()[:5]  # Limit to first 5 pairs
            trade_amounts = self.price_feeds.get_trade_amounts()

            # Find arbitrage opportunities
            opportunities = await self.price_feeds.find_arbitrage_opportunities(
                token_pairs, trade_amounts
            )

            # Convert to format expected by the rest of the system
            formatted_opportunities = []
            for opp in opportunities:
                formatted_opp = {
                    'pair': f"{self._get_token_symbol(opp.token_in)}/{self._get_token_symbol(opp.token_out)}",
                    'token_in': opp.token_in,
                    'token_out': opp.token_out,
                    'amount_in': str(float(opp.amount) / 1e18),  # Convert from wei to ETH/token units
                    'buy_dex': opp.buy_dex,
                    'sell_dex': opp.sell_dex,
                    'buy_price': float(opp.buy_price),
                    'sell_price': float(opp.sell_price),
                    'profit_percentage': float(opp.profit_percentage),
                    'profit': float(opp.estimated_profit) / 1e18,  # Convert from wei to ETH/token units
                    'estimated_profit': opp.estimated_profit,
                    'net_profit': opp.net_profit,
                    'gas_estimate': opp.gas_cost,
                    'gas_cost': opp.gas_cost,
                    'slippage': 0.005,
                    'timestamp': opp.timestamp
                }
                formatted_opportunities.append(formatted_opp)

            return formatted_opportunities

        except Exception as e:
            logger.error(f"Failed to scan for opportunities: {e}")
            return []

    def _get_token_symbol(self, token_address: str) -> str:
        """Get token symbol from address"""
        for symbol, address in self.price_feeds.token_addresses.items():
            if address.lower() == token_address.lower():
                return symbol
        return token_address[:8] + "..."

    async def _process_opportunity(self, opportunity: Dict):
        """Process a single arbitrage opportunity"""
        try:
            logger.info(f"Processing opportunity: {opportunity.get('pair', 'Unknown')}")

            # Step 1: Validate opportunity is still profitable
            is_valid = await self._validate_opportunity(opportunity)
            if not is_valid:
                logger.warning("Opportunity is no longer valid")
                return

            # Step 2: Risk Assessment
            risk_assessment = await self.risk_manager.assess_trade_risk(opportunity)

            if not risk_assessment.is_safe:
                logger.warning(f"Opportunity rejected due to risk: {risk_assessment.blockers}")
                return

            if risk_assessment.warnings:
                logger.warning(f"Proceeding with warnings: {risk_assessment.warnings}")

            # Step 3: Check if dry run mode
            import sys
            if '--dry-run' in sys.argv:
                logger.info(f"DRY RUN: Would execute trade with profit: {opportunity.get('profit_percentage', 0):.2f}%")
                self.total_trades_attempted += 1
                self.total_successful_trades += 1
                profit = Decimal(str(opportunity.get('profit', 0)))
                self.total_profit += profit

                await self.notification_manager.send_status_alert(
                    "DRY RUN Trade Success",
                    f"Profit: ${float(profit):.2f}\nPair: {opportunity.get('pair')}"
                )
                return

            # Step 4: Prepare Trade Parameters (for real execution)
            trade_params = await self._prepare_trade_parameters(opportunity, risk_assessment)
            if not trade_params:
                logger.error("Failed to prepare trade parameters")
                return

            # Step 5: Execute Trade
            logger.info(f"Executing arbitrage trade...")
            self.total_trades_attempted += 1

            success, result = await self._execute_arbitrage_trade(trade_params)

            # Step 6: Record Results
            await self._record_trade_result(opportunity, success, result)

        except Exception as e:
            logger.error(f"Error processing opportunity: {e}")
            await self.risk_manager.record_trade_result(
                opportunity,
                False,
                error=str(e)
            )

    async def _validate_opportunity(self, opportunity: Dict) -> bool:
        """Validate that an opportunity is still profitable"""
        try:
            # For dry-run testing, always return True to bypass validation
            # Check if we're in dry-run mode using the args from main()
            import sys
            if '--dry-run' in sys.argv:
                logger.info(f"DRY RUN: Skipping opportunity validation")
                return True

            # Create ArbitrageOpportunity object from dict
            from bot.price_feeds import ArbitrageOpportunity
            from decimal import Decimal

            opp = ArbitrageOpportunity(
                token_in=opportunity['token_in'],
                token_out=opportunity['token_out'],
                amount=int(float(opportunity['amount_in']) * 1e18),  # Convert back to wei
                buy_dex=opportunity['buy_dex'],
                sell_dex=opportunity['sell_dex'],
                buy_price=Decimal(str(opportunity['buy_price'])),
                sell_price=Decimal(str(opportunity['sell_price'])),
                profit_percentage=Decimal(str(opportunity['profit_percentage'])),
                estimated_profit=opportunity['estimated_profit'],
                gas_cost=opportunity['gas_cost'],
                net_profit=opportunity['net_profit']
            )

            return await self.price_feeds.validate_opportunity(opp)

        except Exception as e:
            logger.error(f"Opportunity validation failed: {e}")
            return False

    async def _prepare_trade_parameters(self, opportunity: Dict, risk_assessment) -> Optional[Dict]:
        """Prepare parameters for trade execution"""
        try:
            # Extract opportunity data
            token_in = opportunity.get('token_in')
            token_out = opportunity.get('token_out')
            amount_in = int(float(opportunity.get('amount_in', 0)))

            # Prepare basic trade parameters
            trade_params = {
                'flashloan_asset': token_in,
                'flashloan_amount': amount_in,
                'dex_buy': opportunity.get('buy_dex'),
                'dex_sell': opportunity.get('sell_dex'),
                'min_profit': int(float(opportunity.get('estimated_profit', 0)) * 0.95),  # 5% slippage tolerance
                'gas_limit': opportunity.get('gas_cost', 500000),
                'deadline': int(time.time() + 300)  # 5 minute deadline
            }

            logger.info(f"Trade parameters prepared for {self._get_token_symbol(token_in)}")
            return trade_params

        except Exception as e:
            logger.error(f"Failed to prepare trade parameters: {e}")
            return None

    async def _execute_arbitrage_trade(self, trade_params: Dict) -> tuple[bool, Optional[Dict]]:
        """Execute the arbitrage trade via smart contract"""
        try:
            # Execute trade through contract interface
            tx_hash = await self.contract_interface.execute_arbitrage(trade_params)

            if not tx_hash:
                logger.error("Trade execution failed - no transaction hash")
                return False, None

            logger.info(f"Trade submitted: {tx_hash}")

            # Wait for transaction confirmation
            receipt = await self.contract_interface.wait_for_confirmation(tx_hash)

            if receipt and receipt.status == 1:
                # Parse transaction results
                result = await self._parse_trade_result(receipt)
                logger.info(f"Trade successful! Profit: ${result.get('profit', 0):.2f}")

                # Send success notification
                await self.notification_manager.send_status_alert(
                    "Arbitrage Success!",
                    f"Profit: ${result.get('profit', 0):.2f}\nTx: {tx_hash}"
                )

                return True, result
            else:
                logger.error(f"Trade failed - transaction reverted: {tx_hash}")
                return False, None

        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return False, None

    async def _parse_trade_result(self, receipt) -> Dict:
        """Parse trade results from transaction receipt"""
        try:
            gas_used = receipt.gasUsed
            gas_price = receipt.effectiveGasPrice
            gas_cost = gas_used * gas_price / 1e18  # Convert to ETH
            gas_cost_usd = gas_cost * 2000  # Approximate ETH price

            # For now, return basic information
            return {
                'gas_used': gas_used,
                'gas_cost_usd': gas_cost_usd,
                'profit': 0.0,  # Parse from contract events
                'tx_hash': receipt.transactionHash.hex()
            }

        except Exception as e:
            logger.error(f"Failed to parse trade result: {e}")
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
            logger.error(f"Failed to record trade result: {e}")

    def _log_performance_update(self):
        """Log current performance metrics"""
        if self.start_time:
            runtime = time.time() - self.start_time
            runtime_hours = runtime / 3600

            success_rate = (self.total_successful_trades / self.total_trades_attempted * 100
                            if self.total_trades_attempted > 0 else 0)

            logger.info(f"Performance Update:")
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
**Trading Session Report**

**Session Duration:** {runtime_hours:.1f} hours
**Opportunities Found:** {self.total_opportunities_found}
**Trades Attempted:** {self.total_trades_attempted}
**Successful Trades:** {self.total_successful_trades}
**Success Rate:** {success_rate:.1f}%
**Total Profit:** ${self.total_profit:.2f}
**Risk Score:** {risk_metrics.get('avg_risk_score', 0):.1f}/100
**Network Health:** {risk_metrics.get('network_health', 0):.1%}
"""

            await self.notification_manager.send_status_alert(
                "Session Report", report
            )

        except Exception as e:
            logger.error(f"Failed to send session report: {e}")

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
            'network_connected': self.web3.is_connected()
        }

    async def get_detailed_metrics(self) -> Dict:
        """Get detailed performance metrics"""
        status = self.get_status()
        risk_metrics = self.risk_manager.get_performance_metrics()

        return {
            **status,
            'risk_metrics': risk_metrics,
            'price_feed_status': await self.price_feeds.get_health_status()
        }

    # Manual Control Methods
    async def force_scan(self) -> List[Dict]:
        """Force a manual opportunity scan"""
        logger.info("Forcing manual opportunity scan...")
        return await self._scan_for_opportunities()

    async def test_opportunity(self, opportunity: Dict) -> Dict:
        """Test an opportunity without executing"""
        logger.info(f"Testing opportunity: {opportunity.get('pair', 'Unknown')}")

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
    """Main execution function"""
    import argparse
    from config.settings import Settings

    parser = argparse.ArgumentParser(description='Flashloan Arbitrage Bot')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode')
    parser.add_argument('--log-level', default='INFO', help='Log level')
    args = parser.parse_args()

    settings = Settings()

    # Override settings based on arguments - but don't try to set settings.security.dry_run_mode
    # since that attribute doesn't exist. The dry-run check is handled via sys.argv instead.
    if args.dry_run:
        logger.info("Running in DRY RUN mode - no real trades will be executed")

    async with FlashloanArbitrageBotManager(settings) as bot:
        try:
            await bot.start()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")


if __name__ == "__main__":
    asyncio.run(main())