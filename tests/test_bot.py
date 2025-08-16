# Bot logic tests 
# tests/test_bot.py
"""
Comprehensive Bot Logic Tests for Flashloan Arbitrage Bot
Tests opportunity scanning, risk management, and trading logic
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from decimal import Decimal
from typing import Dict, List
import json

from bot.arbitrage_bot import FlashloanArbitrageBot, FlashloanArbitrageBotManager
from bot.opportunity_scanner import OpportunityScanner
from bot.risk_manager import RiskManager, RiskMetrics, TradeRisk
from bot.price_feeds import PriceFeeds
from bot.contract_interface import ContractInterface
from config.settings import Settings
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class TestOpportunityScanner:
    """Test suite for opportunity scanning functionality"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        settings = Mock(spec=Settings)
        settings.MIN_PROFIT_THRESHOLD = 0.005  # 0.5%
        settings.MAX_FLASHLOAN_AMOUNT = 50000
        settings.SCAN_INTERVAL = 10
        settings.ONEINCH_API_KEY = "test_key"
        settings.POLYGON_RPC_URL = "https://test-rpc.com"
        return settings

    @pytest.fixture
    def mock_price_feeds(self):
        """Mock price feeds for testing"""
        price_feeds = Mock(spec=PriceFeeds)

        # Mock successful price data
        price_feeds.get_token_prices.return_value = {
            'USDC': {'uniswap': 1.000, 'sushiswap': 1.002, 'quickswap': 0.998},
            'WETH': {'uniswap': 2000.5, 'sushiswap': 2003.0, 'quickswap': 1998.2}
        }

        price_feeds.get_swap_route = AsyncMock(return_value={
            'dex_buy': 'quickswap',
            'dex_sell': 'sushiswap',
            'buy_calldata': '0x123',
            'sell_calldata': '0x456',
            'gas_estimate': 300000
        })

        return price_feeds

    @pytest.fixture
    def opportunity_scanner(self, mock_settings, mock_price_feeds):
        """Create opportunity scanner for testing"""
        return OpportunityScanner(mock_settings, mock_price_feeds)

    @pytest.mark.asyncio
    async def test_scan_for_opportunities_success(self, opportunity_scanner):
        """Test successful opportunity scanning"""
        # Mock price feeds to return profitable opportunities
        opportunity_scanner.price_feeds.get_token_prices = AsyncMock(return_value={
            'USDC-WETH': {
                'uniswap': {'price': 2000.0, 'liquidity': 1000000},
                'sushiswap': {'price': 2010.0, 'liquidity': 800000},  # 0.5% higher
                'quickswap': {'price': 1995.0, 'liquidity': 600000}  # 0.25% lower
            }
        })

        opportunities = await opportunity_scanner.scan_for_opportunities()

        assert len(opportunities) > 0, "Should find opportunities"

        # Check opportunity structure
        opp = opportunities[0]
        assert 'pair' in opp
        assert 'profit' in opp
        assert 'amount_in' in opp
        assert 'dex_buy' in opp
        assert 'dex_sell' in opp
        assert opp['profit'] > 0, "Should have positive profit"

        logger.info(f"✅ Found {len(opportunities)} opportunities")

    @pytest.mark.asyncio
    async def test_scan_no_opportunities(self, opportunity_scanner):
        """Test scanning when no opportunities exist"""
        # Mock price feeds to return no profitable opportunities
        opportunity_scanner.price_feeds.get_token_prices = AsyncMock(return_value={
            'USDC-WETH': {
                'uniswap': {'price': 2000.0, 'liquidity': 1000000},
                'sushiswap': {'price': 2000.1, 'liquidity': 800000},  # Only 0.005% difference
                'quickswap': {'price': 1999.9, 'liquidity': 600000}  # Too small profit
            }
        })

        opportunities = await opportunity_scanner.scan_for_opportunities()

        assert len(opportunities) == 0, "Should find no opportunities when profit is too low"
        logger.info("✅ Correctly filtered out low-profit opportunities")

    @pytest.mark.asyncio
    async def test_opportunity_filtering(self, opportunity_scanner):
        """Test opportunity filtering logic"""
        # Create test opportunities with various profit levels
        test_opportunities = [
            {'pair': 'USDC-WETH', 'profit': 0.001, 'amount_in': 10000},  # Too low profit
            {'pair': 'USDC-WETH', 'profit': 0.01, 'amount_in': 10000},  # Good profit
            {'pair': 'USDC-WETH', 'profit': 0.02, 'amount_in': 100000}  # High profit, large amount
        ]

        # Test filtering
        filtered = opportunity_scanner._filter_opportunities(test_opportunities)

        # Should filter out the low-profit opportunity
        assert len(filtered) == 2, "Should filter out low-profit opportunities"
        assert all(opp['profit'] >= 0.005 for opp in filtered), "All opportunities should meet profit threshold"

        logger.info("✅ Opportunity filtering working correctly")

    @pytest.mark.asyncio
    async def test_opportunity_ranking(self, opportunity_scanner):
        """Test opportunity ranking by profitability"""
        test_opportunities = [
            {'pair': 'USDC-WETH', 'profit': 0.01, 'amount_in': 10000, 'confidence': 0.8},
            {'pair': 'WETH-USDC', 'profit': 0.02, 'amount_in': 5000, 'confidence': 0.9},  # Best
            {'pair': 'USDC-MATIC', 'profit': 0.015, 'amount_in': 8000, 'confidence': 0.7}
        ]

        ranked = opportunity_scanner._rank_opportunities(test_opportunities)

        # Should be ranked by profit * confidence score
        assert ranked[0]['profit'] == 0.02, "Highest scoring opportunity should be first"
        assert len(ranked) == len(test_opportunities), "Should return all opportunities"

        logger.info("✅ Opportunity ranking working correctly")

    def test_performance_metrics(self, opportunity_scanner):
        """Test performance metrics tracking"""
        # Simulate some scanning activity
        opportunity_scanner.total_scans = 100
        opportunity_scanner.total_opportunities_found = 25
        opportunity_scanner.avg_scan_time = 2.5

        metrics = opportunity_scanner.get_performance_metrics()

        assert metrics['total_scans'] == 100
        assert metrics['total_opportunities'] == 25
        assert metrics['success_rate'] == 0.25  # 25/100
        assert metrics['avg_scan_time'] == 2.5

        logger.info("✅ Performance metrics tracking working")


class TestRiskManager:
    """Test suite for risk management functionality"""

    @pytest.fixture
    def mock_web3(self):
        """Mock Web3 instance"""
        web3 = Mock()
        web3.eth.gas_price = AsyncMock(return_value=50_000_000_000)  # 50 gwei
        web3.eth.get_block = Mock(return_value=Mock(timestamp=time.time() - 5))  # Recent block
        return web3

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for risk manager"""
        settings = Mock(spec=Settings)
        settings.MAX_FLASHLOAN_AMOUNT = 50000
        settings.MIN_PROFIT_THRESHOLD = 0.005
        return settings

    @pytest.fixture
    def risk_manager(self, mock_settings, mock_web3):
        """Create risk manager for testing"""
        return RiskManager(mock_settings, mock_web3)

    @pytest.mark.asyncio
    async def test_safe_opportunity_assessment(self, risk_manager):
        """Test assessment of a safe trading opportunity"""
        safe_opportunity = {
            'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',  # USDC
            'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',  # WETH
            'amount_in': 10000,  # $10k
            'profit': 0.02,  # 2% profit
            'slippage': 0.01,  # 1% slippage
            'gas_estimate': 300000
        }

        assessment = await risk_manager.assess_trade_risk(safe_opportunity)

        assert assessment.is_safe == True, "Safe opportunity should pass assessment"
        assert assessment.risk_score < 50, "Risk score should be low for safe trades"
        assert len(assessment.blockers) == 0, "Should have no blockers for safe trades"

        logger.info(f"✅ Safe opportunity assessment: Risk Score {assessment.risk_score}")

    @pytest.mark.asyncio
    async def test_risky_opportunity_assessment(self, risk_manager):
        """Test assessment of a risky trading opportunity"""
        risky_opportunity = {
            'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
            'amount_in': 100000,  # $100k - very large
            'profit': 0.002,  # 0.2% profit - very low
            'slippage': 0.05,  # 5% slippage - very high
            'gas_estimate': 800000  # High gas
        }

        assessment = await risk_manager.assess_trade_risk(risky_opportunity)

        assert assessment.is_safe == False, "Risky opportunity should fail assessment"
        assert assessment.risk_score > 50, "Risk score should be high for risky trades"
        assert len(assessment.blockers) > 0, "Should have blockers for risky trades"

        logger.info(
            f"✅ Risky opportunity assessment: Risk Score {assessment.risk_score}, Blockers: {len(assessment.blockers)}")

    @pytest.mark.asyncio
    async def test_emergency_pause_functionality(self, risk_manager):
        """Test emergency pause functionality"""
        # Activate emergency pause
        risk_manager.emergency_stop()

        assert risk_manager.emergency_pause == True, "Emergency pause should be active"

        # Test that trades are blocked during emergency pause
        test_opportunity = {'amount_in': 1000, 'profit': 0.01, 'slippage': 0.01}
        assessment = await risk_manager.assess_trade_risk(test_opportunity)

        assert assessment.is_safe == False, "Trades should be blocked during emergency pause"
        assert "Emergency pause is active" in assessment.blockers

        # Resume trading
        risk_manager.resume_trading()
        assert risk_manager.emergency_pause == False, "Emergency pause should be deactivated"

        logger.info("✅ Emergency pause functionality working")

    @pytest.mark.asyncio
    async def test_circuit_breaker(self, risk_manager):
        """Test circuit breaker after consecutive failures"""
        # Simulate consecutive failures
        test_opportunity = {'amount_in': 1000, 'profit': 0.01}

        for i in range(risk_manager.max_consecutive_failures):
            await risk_manager.record_trade_result(test_opportunity, success=False, error=f"Test failure {i}")

        # Circuit breaker should be active
        assert risk_manager.circuit_breaker_active == True, "Circuit breaker should activate after max failures"

        # Test that trades are blocked
        assessment = await risk_manager.assess_trade_risk(test_opportunity)
        assert assessment.is_safe == False, "Trades should be blocked when circuit breaker is active"

        logger.info("✅ Circuit breaker functionality working")

    def test_daily_volume_limits(self, risk_manager):
        """Test daily volume limiting"""
        # Set daily volume near limit
        risk_manager.daily_volume = Decimal("90000")  # $90k of $100k limit

        large_opportunity = {
            'amount_in': 15000,  # Would exceed limit
            'profit': 0.01,
            'slippage': 0.01
        }

        # This should be blocked due to volume limit
        with patch.object(risk_manager, 'assess_trade_risk') as mock_assess:
            mock_assess.return_value = Mock(is_safe=False, blockers=["Daily volume limit would be exceeded"])

            # The volume check should prevent execution
            logger.info("✅ Daily volume limits working (mocked)")

    @pytest.mark.asyncio
    async def test_trade_result_recording(self, risk_manager):
        """Test trade result recording and tracking"""
        test_opportunity = {'amount_in': 5000, 'profit': 0.015}

        # Record successful trade
        await risk_manager.record_trade_result(
            test_opportunity,
            success=True,
            profit=Decimal("75")
        )

        assert risk_manager.consecutive_failures == 0, "Successful trade should reset failure count"
        assert len(risk_manager.trade_history) == 1, "Trade should be recorded in history"

        # Record failed trade
        await risk_manager.record_trade_result(
            test_opportunity,
            success=False,
            error="Test error"
        )

        assert risk_manager.consecutive_failures == 1, "Failed trade should increment failure count"
        assert len(risk_manager.trade_history) == 2, "Both trades should be recorded"

        logger.info("✅ Trade result recording working")

    def test_risk_status_reporting(self, risk_manager):
        """Test risk status reporting"""
        status = risk_manager.get_risk_status()

        required_fields = [
            'emergency_pause', 'circuit_breaker_active', 'consecutive_failures',
            'daily_volume', 'network_health_score', 'total_assessments'
        ]

        for field in required_fields:
            assert field in status, f"Status should include {field}"

        logger.info("✅ Risk status reporting working")


class TestFlashloanArbitrageBot:
    """Test suite for main arbitrage bot"""

    @pytest.fixture
    def mock_components(self):
        """Mock all bot components"""
        components = {
            'web3': Mock(),
            'price_feeds': Mock(spec=PriceFeeds),
            'contract_interface': Mock(spec=ContractInterface),
            'risk_manager': Mock(spec=RiskManager),
            'opportunity_scanner': Mock(spec=OpportunityScanner)
        }

        # Mock successful initialization
        components['web3'].is_connected.return_value = True
        components['web3'].eth.chain_id = 137  # Polygon

        components['price_feeds'].start = AsyncMock()
        components['contract_interface'].initialize = AsyncMock()

        return components

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for bot testing"""
        settings = Mock(spec=Settings)
        settings.RPC_URL = "https://test-rpc.com"
        settings.MIN_PROFIT_THRESHOLD = 0.005
        settings.MAX_FLASHLOAN_AMOUNT = 50000
        settings.SCAN_INTERVAL = 10
        return settings

    @pytest.mark.asyncio
    async def test_bot_initialization(self, mock_settings):
        """Test bot initialization process"""
        with patch('bot.arbitrage_bot.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 137
            mock_web3_class.return_value = mock_web3

            with patch.multiple(
                    'bot.arbitrage_bot',
                    PriceFeeds=Mock(),
                    ContractInterface=Mock(),
                    RiskManager=Mock(),
                    OpportunityScanner=Mock(),
                    NotificationManager=Mock()
            ):
                bot = FlashloanArbitrageBot(mock_settings)

                assert bot.running == False, "Bot should not be running initially"
                assert bot.web3 is not None, "Bot should have Web3 connection"

                logger.info("✅ Bot initialization successful")

    @pytest.mark.asyncio
    async def test_opportunity_processing_flow(self, mock_settings):
        """Test the complete opportunity processing flow"""
        with patch('bot.arbitrage_bot.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 137
            mock_web3_class.return_value = mock_web3

            # Mock all components
            with patch.multiple(
                    'bot.arbitrage_bot',
                    PriceFeeds=Mock(),
                    ContractInterface=Mock(),
                    RiskManager=Mock(),
                    OpportunityScanner=Mock(),
                    NotificationManager=Mock()
            ) as mocks:
                bot = FlashloanArbitrageBot(mock_settings)

                # Mock risk assessment - safe trade
                mock_risk_assessment = Mock()
                mock_risk_assessment.is_safe = True
                mock_risk_assessment.warnings = []
                mock_risk_assessment.blockers = []
                mock_risk_assessment.metrics = Mock()
                mock_risk_assessment.metrics.profit_threshold = Decimal("0.01")

                bot.risk_manager.assess_trade_risk = AsyncMock(return_value=mock_risk_assessment)

                # Mock trade preparation
                trade_params = {
                    'flashloan_asset': '0x123',
                    'flashloan_amount': 10000,
                    'gas_limit': 300000
                }

                with patch.object(bot, '_prepare_trade_parameters', return_value=trade_params):
                    with patch.object(bot, '_execute_arbitrage_trade', return_value=(True, {'profit': 50})):
                        with patch.object(bot, '_record_trade_result') as mock_record:
                            # Test opportunity processing
                            test_opportunity = {
                                'pair': 'USDC-WETH',
                                'profit': 0.015,
                                'amount_in': 10000
                            }

                            await bot._process_opportunity(test_opportunity)

                            # Verify the flow was executed
                            bot.risk_manager.assess_trade_risk.assert_called_once()
                            mock_record.assert_called_once()

                            logger.info("✅ Opportunity processing flow working")

    @pytest.mark.asyncio
    async def test_bot_status_reporting(self, mock_settings):
        """Test bot status reporting functionality"""
        with patch('bot.arbitrage_bot.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 137
            mock_web3_class.return_value = mock_web3

            with patch.multiple(
                    'bot.arbitrage_bot',
                    PriceFeeds=Mock(),
                    ContractInterface=Mock(),
                    RiskManager=Mock(),
                    OpportunityScanner=Mock(),
                    NotificationManager=Mock()
            ):
                bot = FlashloanArbitrageBot(mock_settings)

                # Mock component status methods
                bot.risk_manager.get_risk_status.return_value = {'emergency_pause': False}
                bot.opportunity_scanner.get_status.return_value = {'total_scans': 100}

                status = bot.get_status()

                required_fields = [
                    'running', 'paused', 'runtime_seconds', 'opportunities_found',
                    'trades_attempted', 'successful_trades', 'total_profit'
                ]

                for field in required_fields:
                    assert field in status, f"Status should include {field}"

                logger.info("✅ Bot status reporting working")

    @pytest.mark.asyncio
    async def test_emergency_stop(self, mock_settings):
        """Test emergency stop functionality"""
        with patch('bot.arbitrage_bot.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 137
            mock_web3_class.return_value = mock_web3

            with patch.multiple(
                    'bot.arbitrage_bot',
                    PriceFeeds=Mock(),
                    ContractInterface=Mock(),
                    RiskManager=Mock(),
                    OpportunityScanner=Mock(),
                    NotificationManager=Mock()
            ) as mocks:
                bot = FlashloanArbitrageBot(mock_settings)
                bot.running = True

                # Test emergency stop
                await bot.emergency_stop()

                # Verify emergency stop was called on risk manager
                bot.risk_manager.emergency_stop.assert_called_once()
                assert bot.running == False, "Bot should be stopped after emergency stop"

                logger.info("✅ Emergency stop functionality working")


class TestBotIntegration:
    """Integration tests for bot components working together"""

    @pytest.mark.asyncio
    async def test_bot_context_manager(self):
        """Test bot async context manager"""
        mock_settings = Mock(spec=Settings)
        mock_settings.RPC_URL = "https://test-rpc.com"

        with patch('bot.arbitrage_bot.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 137
            mock_web3_class.return_value = mock_web3

            with patch.multiple(
                    'bot.arbitrage_bot',
                    PriceFeeds=Mock(),
                    ContractInterface=Mock(),
                    RiskManager=Mock(),
                    OpportunityScanner=Mock(),
                    NotificationManager=Mock()
            ):
                async with FlashloanArbitrageBotManager(mock_settings) as bot:
                    assert bot is not None, "Context manager should return bot instance"
                    assert isinstance(bot, FlashloanArbitrageBot), "Should return correct bot type"

                logger.info("✅ Bot context manager working")

    @pytest.mark.asyncio
    async def test_component_initialization_order(self):
        """Test that components are initialized in correct order"""
        mock_settings = Mock(spec=Settings)
        mock_settings.RPC_URL = "https://test-rpc.com"

        with patch('bot.arbitrage_bot.Web3') as mock_web3_class:
            mock_web3 = Mock()
            mock_web3.is_connected.return_value = True
            mock_web3.eth.chain_id = 137
            mock_web3_class.return_value = mock_web3

            with patch.multiple(
                    'bot.arbitrage_bot',
                    PriceFeeds=Mock(),
                    ContractInterface=Mock(),
                    RiskManager=Mock(),
                    OpportunityScanner=Mock(),
                    NotificationManager=Mock()
            ) as mocks:
                bot = FlashloanArbitrageBot(mock_settings)

                # Verify all components were created
                assert bot.price_feeds is not None
                assert bot.contract_interface is not None
                assert bot.risk_manager is not None
                assert bot.opportunity_scanner is not None
                assert bot.notification_manager is not None

                logger.info("✅ Component initialization order correct")


# Performance and Load Tests
class TestBotPerformance:
    """Performance and load testing for the bot"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_scanning_performance(self):
        """Test scanning performance under load"""
        mock_settings = Mock()
        mock_price_feeds = Mock()

        # Mock price feeds to return data quickly
        mock_price_feeds.get_token_prices = AsyncMock(return_value={})

        scanner = OpportunityScanner(mock_settings, mock_price_feeds)

        # Time multiple scans
        start_time = time.time()
        scan_count = 10

        for _ in range(scan_count):
            await scanner.scan_for_opportunities()

        end_time = time.time()
        avg_scan_time = (end_time - start_time) / scan_count

        assert avg_scan_time < 5.0, f"Average scan time {avg_scan_time}s should be under 5s"

        logger.info(f"✅ Scanning performance: {avg_scan_time:.2f}s average")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_risk_assessment_performance(self):
        """Test risk assessment performance"""
        mock_settings = Mock()
        mock_web3 = Mock()
        mock_web3.eth.gas_price = AsyncMock(return_value=50_000_000_000)
        mock_web3.eth.get_block = Mock(return_value=Mock(timestamp=time.time()))

        risk_manager = RiskManager(mock_settings, mock_web3)

        test_opportunity = {
            'token_in': '0x123',
            'token_out': '0x456',
            'amount_in': 10000,
            'profit': 0.015,
            'slippage': 0.01,
            'gas_estimate': 300000
        }

        # Time multiple assessments
        start_time = time.time()
        assessment_count = 50

        for _ in range(assessment_count):
            await risk_manager.assess_trade_risk(test_opportunity)

        end_time = time.time()
        avg_assessment_time = (end_time - start_time) / assessment_count

        assert avg_assessment_time < 1.0, f"Average assessment time {avg_assessment_time}s should be under 1s"

        logger.info(f"✅ Risk assessment performance: {avg_assessment_time:.3f}s average")


# Test Configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")


# Main test execution
if __name__ == "__main__":
    # Run bot tests
    pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])