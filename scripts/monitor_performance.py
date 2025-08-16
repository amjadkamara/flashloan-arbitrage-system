# Performance monitoring
# scripts/monitor_performance.py

"""
Performance Monitoring Script
Real-time monitoring and analytics for the flashloan arbitrage bot
"""

import asyncio
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from bot.utils.logger import get_logger
from config.settings import load_settings

logger = get_logger('performance_monitor')


@dataclass
class TradeMetrics:
    """Trade execution metrics"""
    timestamp: datetime
    trade_id: str
    token_pair: str
    amount: float
    profit: float
    gas_cost: float
    execution_time: float
    success: bool
    dex_from: str
    dex_to: str
    price_difference: float
    slippage: float


@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    network_latency: float
    web3_response_time: float
    price_feed_latency: float
    opportunities_found: int
    opportunities_executed: int


class PerformanceMonitor:
    """Real-time performance monitoring system"""

    def __init__(self):
        self.settings = load_settings()
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)

        # Metrics storage
        self.trade_metrics: deque = deque(maxlen=1000)
        self.system_metrics: deque = deque(maxlen=1000)

        # Performance counters
        self.stats = {
            'total_trades': 0,
            'successful_trades': 0,
            'total_profit': 0.0,
            'total_gas_cost': 0.0,
            'average_execution_time': 0.0,
            'best_profit': 0.0,
            'worst_loss': 0.0,
            'uptime_start': datetime.now(),
            'opportunities_found_today': 0,
            'opportunities_executed_today': 0
        }

        # Alerts configuration
        self.alert_thresholds = {
            'low_success_rate': 0.5,  # Below 50%
            'high_gas_cost': 50.0,  # Above $50
            'slow_execution': 30.0,  # Above 30 seconds
            'low_profit_rate': 0.1,  # Below 10%
            'high_memory_usage': 0.8,  # Above 80%
            'high_cpu_usage': 0.8  # Above 80%
        }

        self.running = False

    def start_monitoring(self):
        """Start the performance monitoring system"""
        logger.info("🔍 Starting Performance Monitor")
        self.running = True

        # Start monitoring threads
        threading.Thread(target=self._system_metrics_loop, daemon=True).start()
        threading.Thread(target=self._log_analyzer_loop, daemon=True).start()
        threading.Thread(target=self._alert_system_loop, daemon=True).start()

        # Main monitoring loop
        self._main_monitor_loop()

    def stop_monitoring(self):
        """Stop monitoring"""
        logger.info("⏹️ Stopping Performance Monitor")
        self.running = False
        self._save_session_report()

    def _main_monitor_loop(self):
        """Main monitoring display loop"""
        try:
            while self.running:
                self._display_dashboard()
                time.sleep(5)  # Update every 5 seconds
        except KeyboardInterrupt:
            self.stop_monitoring()

    def _display_dashboard(self):
        """Display real-time dashboard"""
        # Clear screen
        import os
        os.system('cls' if os.name == 'nt' else 'clear')

        print("🚀 FLASHLOAN ARBITRAGE BOT - PERFORMANCE DASHBOARD")
        print("=" * 80)

        # Current time and uptime
        now = datetime.now()
        uptime = now - self.stats['uptime_start']
        print(f"🕐 Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️ Uptime: {self._format_duration(uptime)}")
        print()

        # Trading performance
        print("📈 TRADING PERFORMANCE")
        print("-" * 40)
        success_rate = (self.stats['successful_trades'] / max(self.stats['total_trades'], 1)) * 100
        profit_per_trade = self.stats['total_profit'] / max(self.stats['successful_trades'], 1)

        print(f"Total Trades: {self.stats['total_trades']}")
        print(f"Successful: {self.stats['successful_trades']} ({success_rate:.1f}%)")
        print(f"Total Profit: ${self.stats['total_profit']:.2f}")
        print(f"Total Gas Cost: ${self.stats['total_gas_cost']:.2f}")
        print(f"Net Profit: ${self.stats['total_profit'] - self.stats['total_gas_cost']:.2f}")
        print(f"Avg Profit/Trade: ${profit_per_trade:.2f}")
        print(f"Best Trade: ${self.stats['best_profit']:.2f}")
        print(f"Worst Trade: ${self.stats['worst_loss']:.2f}")
        print(f"Avg Execution Time: {self.stats['average_execution_time']:.2f}s")
        print()

        # Opportunity analysis
        print("🎯 OPPORTUNITY ANALYSIS")
        print("-" * 40)
        execution_rate = (self.stats['opportunities_executed_today'] /
                          max(self.stats['opportunities_found_today'], 1)) * 100
        print(f"Opportunities Found Today: {self.stats['opportunities_found_today']}")
        print(f"Opportunities Executed Today: {self.stats['opportunities_executed_today']}")
        print(f"Execution Rate: {execution_rate:.1f}%")
        print()

        # Recent trades
        print("📊 RECENT TRADES (Last 5)")
        print("-" * 40)
        recent_trades = list(self.trade_metrics)[-5:]
        if recent_trades:
            for trade in reversed(recent_trades):
                status = "✅" if trade.success else "❌"
                print(f"{status} {trade.timestamp.strftime('%H:%M:%S')} "
                      f"{trade.token_pair} ${trade.profit:.2f} "
                      f"({trade.execution_time:.1f}s)")
        else:
            print("No recent trades")
        print()

        # System metrics
        if self.system_metrics:
            latest = self.system_metrics[-1]
            print("🖥️ SYSTEM METRICS")
            print("-" * 40)
            print(f"CPU Usage: {latest.cpu_usage:.1f}%")
            print(f"Memory Usage: {latest.memory_usage:.1f}%")
            print(f"Network Latency: {latest.network_latency:.0f}ms")
            print(f"Web3 Response: {latest.web3_response_time:.0f}ms")
            print(f"Price Feed Latency: {latest.price_feed_latency:.0f}ms")
            print()

        # Alerts
        alerts = self._check_alerts()
        if alerts:
            print("🚨 ACTIVE ALERTS")
            print("-" * 40)
            for alert in alerts:
                print(f"⚠️ {alert}")
            print()

        print("💡 Press Ctrl+C to stop monitoring and generate report")

    def _system_metrics_loop(self):
        """Background system metrics collection"""
        import psutil

        while self.running:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()

                # Network and Web3 metrics (mock for now)
                network_latency = self._measure_network_latency()
                web3_response_time = self._measure_web3_response()
                price_feed_latency = self._measure_price_feed_latency()

                metrics = SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_usage=cpu_percent,
                    memory_usage=memory.percent,
                    network_latency=network_latency,
                    web3_response_time=web3_response_time,
                    price_feed_latency=price_feed_latency,
                    opportunities_found=self.stats['opportunities_found_today'],
                    opportunities_executed=self.stats['opportunities_executed_today']
                )

                self.system_metrics.append(metrics)

                # Save metrics periodically
                if len(self.system_metrics) % 60 == 0:  # Every 5 minutes
                    self._save_metrics()

            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")

            time.sleep(5)

    def _log_analyzer_loop(self):
        """Analyze bot logs for trade metrics"""
        log_file = Path(__file__).parent.parent / 'logs' / 'arbitrage_bot.log'

        if not log_file.exists():
            return

        # Monitor log file for new trades
        processed_lines = 0

        while self.running:
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()

                # Process new lines
                for line in lines[processed_lines:]:
                    self._parse_log_line(line.strip())

                processed_lines = len(lines)

            except Exception as e:
                logger.error(f"Error analyzing logs: {e}")

            time.sleep(2)

    def _alert_system_loop(self):
        """Background alert monitoring"""
        while self.running:
            try:
                alerts = self._check_alerts()

                # Send critical alerts
                for alert in alerts:
                    if "CRITICAL" in alert:
                        logger.warning(f"🚨 {alert}")

            except Exception as e:
                logger.error(f"Error in alert system: {e}")

            time.sleep(30)  # Check every 30 seconds

    def _parse_log_line(self, line: str):
        """Parse log line for trade information"""
        try:
            # Look for trade completion logs
            if "Trade completed" in line and "profit:" in line:
                # Extract trade information (simplified parsing)
                parts = line.split()
                timestamp_str = " ".join(parts[:2])
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

                # Extract metrics (this would be more sophisticated in practice)
                profit = float([p.replace('$', '').replace(',', '')
                                for p in parts if p.startswith('$')][0])

                trade_metrics = TradeMetrics(
                    timestamp=timestamp,
                    trade_id=f"trade_{int(time.time())}",
                    token_pair="USDC/WETH",  # Default
                    amount=1000.0,  # Default
                    profit=profit,
                    gas_cost=5.0,  # Default
                    execution_time=15.0,  # Default
                    success=profit > 0,
                    dex_from="Uniswap",  # Default
                    dex_to="SushiSwap",  # Default
                    price_difference=0.5,  # Default
                    slippage=0.1  # Default
                )

                self._record_trade(trade_metrics)

        except Exception as e:
            logger.debug(f"Error parsing log line: {e}")

    def _record_trade(self, trade: TradeMetrics):
        """Record a trade in metrics"""
        self.trade_metrics.append(trade)

        # Update statistics
        self.stats['total_trades'] += 1
        if trade.success:
            self.stats['successful_trades'] += 1
            self.stats['total_profit'] += trade.profit
            self.stats['best_profit'] = max(self.stats['best_profit'], trade.profit)
        else:
            self.stats['worst_loss'] = min(self.stats['worst_loss'], trade.profit)

        self.stats['total_gas_cost'] += trade.gas_cost

        # Update average execution time
        total_time = (self.stats['average_execution_time'] * (self.stats['total_trades'] - 1) +
                      trade.execution_time)
        self.stats['average_execution_time'] = total_time / self.stats['total_trades']

    def _measure_network_latency(self) -> float:
        """Measure network latency (simplified)"""
        try:
            import subprocess
            result = subprocess.run(['ping', '-c', '1', '8.8.8.8'],
                                    capture_output=True, text=True, timeout=5)
            # Extract latency from ping output (simplified)
            return 50.0  # Default value
        except:
            return 100.0  # Default high latency

    def _measure_web3_response(self) -> float:
        """Measure Web3 provider response time"""
        # This would connect to actual Web3 provider
        return 200.0  # Default value in ms

    def _measure_price_feed_latency(self) -> float:
        """Measure price feed response time"""
        # This would test actual price feeds
        return 150.0  # Default value in ms

    def _check_alerts(self) -> List[str]:
        """Check for alert conditions"""
        alerts = []

        if self.stats['total_trades'] > 0:
            success_rate = self.stats['successful_trades'] / self.stats['total_trades']
            if success_rate < self.alert_thresholds['low_success_rate']:
                alerts.append(f"CRITICAL: Low success rate ({success_rate:.1%})")

        if self.stats['average_execution_time'] > self.alert_thresholds['slow_execution']:
            alerts.append(f"WARNING: Slow execution time ({self.stats['average_execution_time']:.1f}s)")

        if self.system_metrics:
            latest = self.system_metrics[-1]

            if latest.cpu_usage > self.alert_thresholds['high_cpu_usage'] * 100:
                alerts.append(f"WARNING: High CPU usage ({latest.cpu_usage:.1f}%)")

            if latest.memory_usage > self.alert_thresholds['high_memory_usage'] * 100:
                alerts.append(f"WARNING: High memory usage ({latest.memory_usage:.1f}%)")

            if latest.network_latency > 1000:
                alerts.append(f"CRITICAL: High network latency ({latest.network_latency:.0f}ms)")

        return alerts

    def _save_metrics(self):
        """Save metrics to file"""
        try:
            metrics_file = self.data_dir / f"metrics_{datetime.now().strftime('%Y%m%d')}.json"

            data = {
                'stats': self.stats.copy(),
                'trade_metrics': [asdict(trade) for trade in self.trade_metrics],
                'system_metrics': [asdict(metric) for metric in self.system_metrics]
            }

            # Convert datetime objects to strings
            def convert_datetime(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return obj

            # Recursively convert datetime objects
            def convert_data(data):
                if isinstance(data, dict):
                    return {k: convert_data(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [convert_data(item) for item in data]
                else:
                    return convert_datetime(data)

            converted_data = convert_data(data)

            with open(metrics_file, 'w') as f:
                json.dump(converted_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving metrics: {e}")

    def _save_session_report(self):
        """Generate and save session report"""
        logger.info("📊 Generating session report...")

        report_file = self.data_dir / f"session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(report_file, 'w') as f:
            f.write("FLASHLOAN ARBITRAGE BOT - SESSION REPORT\n")
            f.write("=" * 50 + "\n\n")

            # Session summary
            f.write(f"Session Start: {self.stats['uptime_start']}\n")
            f.write(f"Session End: {datetime.now()}\n")
            f.write(f"Duration: {self._format_duration(datetime.now() - self.stats['uptime_start'])}\n\n")

            # Trading performance
            f.write("TRADING PERFORMANCE\n")
            f.write("-" * 30 + "\n")
            f.write(f"Total Trades: {self.stats['total_trades']}\n")
            f.write(f"Successful Trades: {self.stats['successful_trades']}\n")
            success_rate = (self.stats['successful_trades'] / max(self.stats['total_trades'], 1)) * 100
            f.write(f"Success Rate: {success_rate:.1f}%\n")
            f.write(f"Total Profit: ${self.stats['total_profit']:.2f}\n")
            f.write(f"Total Gas Cost: ${self.stats['total_gas_cost']:.2f}\n")
            f.write(f"Net Profit: ${self.stats['total_profit'] - self.stats['total_gas_cost']:.2f}\n")
            f.write(f"Average Execution Time: {self.stats['average_execution_time']:.2f}s\n\n")

            # Best/Worst trades
            if self.trade_metrics:
                f.write("TRADE ANALYSIS\n")
                f.write("-" * 30 + "\n")
                trades_list = list(self.trade_metrics)
                profitable_trades = [t for t in trades_list if t.success]

                if profitable_trades:
                    best_trade = max(profitable_trades, key=lambda x: x.profit)
                    f.write(f"Best Trade: ${best_trade.profit:.2f} at {best_trade.timestamp}\n")

                if trades_list:
                    worst_trade = min(trades_list, key=lambda x: x.profit)
                    f.write(f"Worst Trade: ${worst_trade.profit:.2f} at {worst_trade.timestamp}\n")

        logger.success(f"📄 Session report saved: {report_file}")

    def _format_duration(self, duration: timedelta) -> str:
        """Format duration for display"""
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def main():
    """Main monitoring function"""
    try:
        monitor = PerformanceMonitor()
        monitor.start_monitoring()

    except KeyboardInterrupt:
        logger.info("\n⏹️ Monitoring stopped by user")
    except Exception as e:
        logger.error(f"\n💥 Monitoring error: {e}")
    finally:
        logger.info("👋 Performance monitoring session ended")


if __name__ == "__main__":
    main()