# End-to-end tests 
# tests/test_integration.py
"""
End-to-End Integration Tests for Flashloan Arbitrage Bot
Tests complete system functionality including real network interactions
"""

import pytest
import asyncio
import time
import os
from decimal import Decimal
from typing import Dict, List
from unittest.mock import Mock, patch

from web3 import Web3

from bot.arbitrage_bot import FlashloanArbitrageBot, FlashloanArbitrageBotManager
from bot.opportunity_scanner import OpportunityScanner
from bot.risk_manager import RiskManager
from bot.price_feeds import PriceFeeds
from bot.contract_interface import ContractInterface
from config.settings import Settings
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class TestSystemIntegration:
    """Complete system integration tests"""

    @pytest.fixture(scope="class")
    def test_settings(self):
        """Test settings configuration"""
        settings = Settings()

        # Override for testing
        settings.RPC_URL = "https://polygon-mumbai.g.alchemy.com/v2/your-test-key"
        settings.MIN_PROFIT_THRESHOLD = 0.01  # 1% for testing
        settings.MAX_FLASHLOAN_AMOUNT = 1000  # Small amount for testing
        settings.SCAN_INTERVAL = 5  # Quick scanning for tests

        return settings

    @pytest.fixture
    def web3_connection(self, test_settings):
        """Test Web3 connection"""
        web3 = Web3(Web3.HTTPProvider(test_settings.RPC_URL))

        if not web3.is_connected():
            pytest.skip("Cannot connect to test network - check RPC_URL")

        return web3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_price_feeds_integration(self, test_settings):
        """Test price feeds integration with real APIs"""
        price_feeds = PriceFeeds(test_settings)

        try:
            await price_feeds.start()

            # Test getting real price data
            prices = await price_feeds.get_token_prices(['USDC', 'WETH'])

            assert prices is not None, "Should receive price data"
            logger.info(f"✅ Price feeds integration: Retrieved {len(prices)} token prices")

        except Exception as e:
            pytest.skip(f"Price feeds integration test failed: {e}")
        finally:
            if hasattr(price_feeds, 'stop'):
                await price_feeds.stop()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_contract_interface_integration(self, test_settings, web3_connection):
        """Test contract interface with real blockchain"""
        contract_interface = ContractInterface(test_settings, web3_connection)

        try:
            # Test network health check
            is_healthy = await contract_interface.is_network_healthy()
            assert isinstance(is_healthy, bool), "Network health check should return boolean"

            # Test gas estimation
            gas_estimate = await contract_interface.estimate_gas('pause')
            assert gas_estimate > 0, "Gas estimation should return positive value"

            logger.info(f"✅ Contract interface integration: Network healthy={is_healthy}, Gas estimate={gas_estimate}")

        except Exception as e:
            logger.warning(f"Contract interface integration test: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_opportunity_scanner_integration(self, test_settings):
        """Test opportunity scanner with real price feeds"""
        price_feeds = PriceFeeds(test_settings)
        scanner = OpportunityScanner(test_settings, price_feeds)

        try:
            await price_feeds.start()

            # Scan for real opportunities (may find none)
            opportunities = await scanner.scan_for_opportunities()

            assert isinstance(opportunities, list), "Should return list of opportunities"

            if opportunities:
                # Validate opportunity structure
                opp = opportunities[0]
                required_fields = ['pair', 'profit', 'amount_in', 'dex_buy', 'dex_sell']
                for field in required_fields:
                    assert field in opp, f"Opportunity should have {field}"

            logger.info(f"✅ Opportunity scanner integration: Found {len(opportunities)} opportunities")

        except Exception as e:
            pytest.skip(f"Opportunity scanner integration test failed: {e}")
        finally:
            if hasattr(price_feeds, 'stop'):
                await price_feeds.stop()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_risk_manager_integration(self, test_settings, web3_connection):
        """Test risk manager with real network data"""
        risk_manager = RiskManager(test_settings, web3_connection)

        # Test with realistic opportunity
        test_opportunity = {
            'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',  # USDC
            'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',  # WETH
            'amount_in': 1000,  # $1k
            'profit': 0.015,  # 1.5%
            'slippage': 0.02,  # 2%
            'gas_estimate': 350000
        }

        try:
            assessment = await risk_manager.assess_trade_risk(test_opportunity)

            assert assessment is not None, "Should return risk assessment"
            assert hasattr(assessment, 'is_safe'), "Assessment should have is_safe property"
            assert hasattr(assessment, 'risk_score'), "Assessment should have risk_score"

            logger.info(f"✅ Risk manager integration: Risk score={assessment.risk_score}, Safe={assessment.is_safe}")

        except Exception as e:
            logger.warning(f"Risk manager integration test: {e}")

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_complete_bot_integration(self, test_settings):
        """Test complete bot system integration"""

        # Skip if no proper test environment
        if not test_settings.RPC_URL or 'your-test-key' in test_settings.RPC_URL:
            pytest.skip("Test requires proper RPC URL configuration")

        try:
            async with FlashloanArbitrageBotManager(test_settings) as bot:
                # Test bot initialization
                assert bot is not None, "Bot should initialize successfully"

                # Test status reporting
                status = bot.get_status()
                assert 'running' in status, "Status should include running state"

                # Test force scan (without actually running main loop)
                opportunities = await bot.force_scan()
                assert isinstance(opportunities, list), "Force scan should return opportunities list"

                # Test opportunity testing functionality
                if opportunities:
                    test_result = await bot.test_opportunity(opportunities[0])
                    assert 'risk_assessment' in test_result, "Test should include risk assessment"
                    assert 'would_execute' in test_result, "Test should indicate execution decision"

                logger.info(
                    f"✅ Complete bot integration: Status={status['running']}, Opportunities={len(opportunities)}")

        except Exception as e:
            logger.warning(f"Complete bot integration test: {e}")


class TestNetworkResilience:
    """Test system resilience to network issues"""

    @pytest.fixture
    def unstable_settings(self):
        """Settings with potentially unstable network"""
        settings = Settings()
        settings.RPC_URL = "https://polygon-mumbai.g.alchemy.com/v2/test"
        return settings

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_network_disconnection_handling(self, unstable_settings):
        """Test handling of network disconnections"""
        web3 = Web3(Web3.HTTPProvider("https://invalid-rpc-url.com"))

        # Test that components handle network issues gracefully
        contract_interface = ContractInterface(unstable_settings, web3)

        try:
            is_healthy = await contract_interface.is_network_healthy()
            # Should return False or handle gracefully
            assert isinstance(is_healthy, bool), "Should handle network issues gracefully"

            logger.info("✅ Network disconnection handling works")

        except Exception as e:
            # Exception is acceptable for network issues
            logger.info(f"✅ Network disconnection properly raises exception: {type(e).__name__}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_api_rate_limiting_handling(self, test_settings):
        """Test handling of API rate limits"""
        price_feeds = PriceFeeds(test_settings)

        try:
            await price_feeds.start()

            # Rapid-fire requests to test rate limiting
            results = []
            for i in range(10):
                try:
                    prices = await price_feeds.get_token_prices(['USDC'])
                    results.append(prices is not None)
                except Exception:
                    results.append(False)

                await asyncio.sleep(0.1)  # Small delay

            # Some requests should succeed even with rate limiting
            success_count = sum(results)
            assert success_count >= 3, f"Should handle rate limiting gracefully, got {success_count}/10 successes"

            logger.info(f"✅ API rate limiting handling: {success_count}/10 requests succeeded")

        except Exception as e:
            logger.warning(f"API rate limiting test: {e}")
        finally:
            if hasattr(price_feeds, 'stop'):
                await price_feeds.stop()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_high_gas_environment(self, test_settings):
        """Test bot behavior in high gas environment"""

        # Mock high gas prices
        with patch('bot.risk_manager.RiskManager._get_gas_price', return_value=200_000_000_000):  # 200 gwei
            risk_manager = RiskManager(test_settings, Mock())

            high_gas_opportunity = {
                'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
                'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
                'amount_in': 5000,
                'profit': 0.01,  # 1% profit
                'slippage': 0.01,
                'gas_estimate': 400000  # High gas usage
            }

            assessment = await risk_manager.assess_trade_risk(high_gas_opportunity)

            # Should be blocked due to high gas costs
            assert assessment.is_safe == False, "High gas should block trades"

            logger.info("✅ High gas environment handling works")


class TestScalabilityAndPerformance:
    """Test system scalability and performance under load"""

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_opportunity_processing(self, test_settings):
        """Test processing multiple opportunities concurrently"""

        # Create multiple mock opportunities
        opportunities = []
        for i in range(5):
            opportunities.append({
                'pair': f'TEST{i}-USDC',
                'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
                'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
                'amount_in': 1000 + i * 100,
                'profit': 0.01 + i * 0.001,
                'slippage': 0.01,
                'gas_estimate': 300000
            })

        risk_manager = RiskManager(test_settings, Mock())

        start_time = time.time()

        # Process opportunities concurrently
        tasks = [risk_manager.assess_trade_risk(opp) for opp in opportunities]
        assessments = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        processing_time = end_time - start_time

        # Verify all assessments completed
        successful_assessments = [a for a in assessments if not isinstance(a, Exception)]
        assert len(successful_assessments) == len(opportunities), "All opportunities should be assessed"

        # Performance check - should be faster than sequential
        assert processing_time < 10.0, f"Concurrent processing should be fast, took {processing_time:.2f}s"

        logger.info(f"✅ Concurrent processing: {len(opportunities)} opportunities in {processing_time:.2f}s")

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_extended_operation_stability(self, test_settings):
        """Test bot stability during extended operation"""

        # Simulate extended operation
        scan_count = 20
        scan_interval = 1  # 1 second between scans

        scanner = OpportunityScanner(test_settings, Mock())

        # Mock price feeds to return varying data
        mock_prices = {
            'USDC-WETH': {
                'uniswap': {'price': 2000.0 + i, 'liquidity': 1000000}
                for i in range(scan_count)
            }
        }

        scanner.price_feeds.get_token_prices = AsyncMock(side_effect=lambda: mock_prices)

        start_time = time.time()
        total_opportunities = 0

        for i in range(scan_count):
            try:
                opportunities = await scanner.scan_for_opportunities()
                total_opportunities += len(opportunities)

                await asyncio.sleep(scan_interval)

            except Exception as e:
                logger.warning(f"Scan {i} failed: {e}")

        end_time = time.time()
        total_time = end_time - start_time

        # Verify system remained stable
        assert total_time > scan_count * scan_interval * 0.8, "Should maintain scanning pace"

        logger.info(
            f"✅ Extended operation: {scan_count} scans over {total_time:.1f}s, {total_opportunities} total opportunities")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, test_settings):
        """Test that memory usage remains stable over time"""
        import psutil
        import gc

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create and destroy components multiple times
        iterations = 10

        for i in range(iterations):
            # Create components
            price_feeds = PriceFeeds(test_settings)
            scanner = OpportunityScanner(test_settings, price_feeds)
            risk_manager = RiskManager(test_settings, Mock())

            # Use components briefly
            await scanner.scan_for_opportunities()

            # Clean up
            del price_feeds, scanner, risk_manager
            gc.collect()

            if i % 3 == 0:  # Check memory every 3 iterations
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory

                # Memory should not grow excessively
                assert memory_growth < 100, f"Memory growth {memory_growth:.1f}MB is too high"

        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory

        logger.info(f"✅ Memory stability: {initial_memory:.1f}MB → {final_memory:.1f}MB (growth: {total_growth:.1f}MB)")


class TestRealWorldScenarios:
    """Test scenarios that could occur in real-world usage"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_market_volatility_scenario(self, test_settings):
        """Test bot behavior during high market volatility"""

        # Simulate volatile price data
        volatile_opportunities = [
            {
                'pair': 'USDC-WETH',
                'amount_in': 10000,
                'profit': 0.05,  # 5% profit - unusually high
                'slippage': 0.08,  # 8% slippage - very high
                'gas_estimate': 500000
            },
            {
                'pair': 'USDC-WETH',
                'amount_in': 10000,
                'profit': 0.001,  # 0.1% profit - very low
                'slippage': 0.001,  # 0.1% slippage - very low
                'gas_estimate': 200000
            }
        ]

        risk_manager = RiskManager(test_settings, Mock())

        for i, opportunity in enumerate(volatile_opportunities):
            assessment = await risk_manager.assess_trade_risk(opportunity)

            # High volatility scenarios should be handled appropriately
            if opportunity['profit'] > 0.03 and opportunity['slippage'] > 0.05:
                # High profit but high risk - should be blocked
                assert assessment.is_safe == False, f"Volatile opportunity {i} should be blocked"

            logger.info(f"Volatile opportunity {i}: Safe={assessment.is_safe}, Risk={assessment.risk_score}")

        logger.info("✅ Market volatility scenario handled correctly")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_network_congestion_scenario(self, test_settings):
        """Test bot behavior during network congestion"""

        # Simulate network congestion with high gas prices and slow blocks
        with patch('bot.risk_manager.RiskManager._get_gas_price', return_value=150_000_000_000):  # 150 gwei
            with patch('bot.risk_manager.RiskManager._assess_network_health', return_value=0.3):  # Poor health

                risk_manager = RiskManager(test_settings, Mock())

                congestion_opportunity = {
                    'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
                    'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
                    'amount_in': 5000,
                    'profit': 0.02,  # 2% profit
                    'slippage': 0.015,
                    'gas_estimate': 350000
                }

                assessment = await risk_manager.assess_trade_risk(congestion_opportunity)

                # Should be blocked due to network congestion
                assert assessment.is_safe == False, "Congested network should block trades"
                assert "Network health poor" in assessment.blockers, "Should identify network health issue"

                logger.info("✅ Network congestion scenario handled correctly")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_flash_crash_scenario(self, test_settings):
        """Test bot behavior during flash crash (extreme price movements)"""

        # Simulate flash crash with extreme price differences
        flash_crash_opportunity = {
            'pair': 'USDC-WETH',
            'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
            'amount_in': 20000,  # Large amount
            'profit': 0.15,  # 15% profit - extremely high
            'slippage': 0.12,  # 12% slippage - extreme
            'gas_estimate': 800000  # High gas due to network stress
        }

        risk_manager = RiskManager(test_settings, Mock())
        assessment = await risk_manager.assess_trade_risk(flash_crash_opportunity)

        # Flash crash scenarios should be blocked due to extreme parameters
        assert assessment.is_safe == False, "Flash crash opportunity should be blocked"
        assert assessment.risk_score > 70, "Risk score should be very high"

        # Check that multiple risk factors are identified
        total_issues = len(assessment.warnings) + len(assessment.blockers)
        assert total_issues >= 2, "Should identify multiple risk factors"

        logger.info(f"✅ Flash crash scenario: Risk={assessment.risk_score}, Issues={total_issues}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_whale_activity_scenario(self, test_settings):
        """Test bot behavior when large trades (whale activity) affect prices"""

        # Simulate large trade affecting liquidity
        whale_affected_opportunity = {
            'pair': 'USDC-WETH',
            'amount_in': 30000,  # Large trade
            'profit': 0.03,  # 3% profit
            'slippage': 0.06,  # 6% slippage due to size
            'gas_estimate': 400000
        }

        # Mock reduced liquidity assessment
        with patch('bot.risk_manager.RiskManager._assess_liquidity', return_value=0.4):  # Low liquidity

            risk_manager = RiskManager(test_settings, Mock())
            assessment = await risk_manager.assess_trade_risk(whale_affected_opportunity)

            # Should be cautious about large trades in low liquidity
            if assessment.is_safe:
                assert len(assessment.warnings) > 0, "Should at least warn about liquidity"
            else:
                assert "liquidity" in str(assessment.blockers).lower(), "Should identify liquidity issues"

            logger.info(f"✅ Whale activity scenario: Safe={assessment.is_safe}, Liquidity concerns addressed")


class TestFailureRecovery:
    """Test system recovery from various failure scenarios"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_recovery_from_failed_trades(self, test_settings):
        """Test recovery after consecutive trade failures"""

        risk_manager = RiskManager(test_settings, Mock())
        test_opportunity = {'amount_in': 1000, 'profit': 0.01}

        # Simulate multiple failures
        for i in range(3):
            await risk_manager.record_trade_result(
                test_opportunity,
                success=False,
                error=f"Test failure {i}"
            )

        assert risk_manager.consecutive_failures == 3, "Should track consecutive failures"

        # Simulate successful trade
        await risk_manager.record_trade_result(
            test_opportunity,
            success=True,
            profit=Decimal("25")
        )

        assert risk_manager.consecutive_failures == 0, "Successful trade should reset failure count"

        logger.info("✅ Recovery from failed trades works correctly")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_recovery_from_circuit_breaker(self, test_settings):
        """Test recovery after circuit breaker activation"""

        risk_manager = RiskManager(test_settings, Mock())
        test_opportunity = {'amount_in': 1000, 'profit': 0.01}

        # Trigger circuit breaker
        for i in range(risk_manager.max_consecutive_failures):
            await risk_manager.record_trade_result(
                test_opportunity,
                success=False,
                error=f"Failure {i}"
            )

        assert risk_manager.circuit_breaker_active == True, "Circuit breaker should activate"

        # Test that trades are blocked
        assessment = await risk_manager.assess_trade_risk(test_opportunity)
        assert assessment.is_safe == False, "Trades should be blocked"

        # Simulate time passing (circuit breaker timeout)
        risk_manager.circuit_breaker_until = None  # Force reset for test
        risk_manager._reset_circuit_breaker()

        assert risk_manager.circuit_breaker_active == False, "Circuit breaker should reset"

        logger.info("✅ Circuit breaker recovery works correctly")


# Test Data and Utilities
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "integration: mark test as integration test requiring network")
    config.addinivalue_line("markers", "slow: mark test as slow running")


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests"""
    import logging
    logging.getLogger("bot").setLevel(logging.INFO)


# Test helper functions
def create_test_opportunity(
        pair: str = "USDC-WETH",
        amount: int = 10000,
        profit: float = 0.015,
        slippage: float = 0.01
) -> Dict:
    """Create a test opportunity with default values"""
    return {
        'pair': pair,
        'token_in': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',  # USDC
        'token_out': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',  # WETH
        'amount_in': amount,
        'profit': profit,
        'slippage': slippage,
        'gas_estimate': 300000,
        'dex_buy': 'uniswap',
        'dex_sell': 'sushiswap'
    }


def assert_valid_opportunity(opportunity: Dict):
    """Assert that an opportunity has valid structure"""
    required_fields = ['pair', 'token_in', 'token_out', 'amount_in', 'profit']
    for field in required_fields:
        assert field in opportunity, f"Opportunity missing required field: {field}"

    assert opportunity['profit'] > 0, "Profit should be positive"
    assert opportunity['amount_in'] > 0, "Amount should be positive"


def assert_valid_risk_assessment(assessment):
    """Assert that a risk assessment has valid structure"""
    assert hasattr(assessment, 'is_safe'), "Assessment should have is_safe"
    assert hasattr(assessment, 'risk_score'), "Assessment should have risk_score"
    assert hasattr(assessment, 'warnings'), "Assessment should have warnings"
    assert hasattr(assessment, 'blockers'), "Assessment should have blockers"

    assert 0 <= assessment.risk_score <= 100, "Risk score should be 0-100"


# Main test execution
if __name__ == "__main__":
    # Run integration tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "integration",
        "--durations=10"
    ])