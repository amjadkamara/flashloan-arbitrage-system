# bot/utils/notifications.py
"""
Enhanced notification system for the flashloan arbitrage bot.

Features:
- Environment-based control (disable dry-run notifications)
- Smart batching (group similar events)
- Profit thresholds (only notify for profits above $X)
- Time-based quiet hours
- Rate limiting to prevent spam

Supports multiple notification channels:
- Discord webhooks
- Telegram bot messages
- Slack webhooks
- Email alerts (SMTP)

Usage:
    from bot.utils.notifications import NotificationManager

    notifier = NotificationManager()
    notifier.send_profit_alert("USDC/WETH", 2.5, "150.25 MATIC")
    notifier.send_error_alert("Transaction failed", "0x123...")
"""

import smtplib
import json
import os
import sys
from datetime import datetime, time as dt_time
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from collections import defaultdict, deque
import asyncio
import aiohttp

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class NotificationConfig:
    """Enhanced configuration for notification channels."""

    # Discord
    discord_webhook_url: Optional[str] = None
    discord_username: str = "Arbitrage Bot"
    discord_avatar_url: Optional[str] = None

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Slack
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#trading"
    slack_username: str = "Arbitrage Bot"

    # Email
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: List[str] = None

    # Enhanced settings
    enabled_channels: List[str] = None  # ["discord", "telegram", "slack", "email"]
    min_profit_alert: float = 1.0  # Minimum profit % for alerts
    max_alerts_per_hour: int = 20

    # Environment-based controls
    dry_run_notifications: bool = False  # Disable notifications during dry runs
    profit_notification_threshold: float = 5.0  # Only notify for profits > $X
    batch_notifications: bool = True  # Group similar events

    # Time-based controls
    notification_quiet_start: str = "23:00"  # Quiet hours start
    notification_quiet_end: str = "07:00"  # Quiet hours end
    notification_timezone: str = "UTC"  # Timezone for quiet hours

    def __post_init__(self):
        if self.enabled_channels is None:
            self.enabled_channels = []
        if self.email_to is None:
            self.email_to = []

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        return cls(
            # Discord
            discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL'),

            # Telegram
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),

            # Enhanced settings
            dry_run_notifications=os.getenv('DRY_RUN_NOTIFICATIONS', 'false').lower() == 'true',
            profit_notification_threshold=float(os.getenv('PROFIT_NOTIFICATION_THRESHOLD', '5.0')),
            batch_notifications=os.getenv('BATCH_NOTIFICATIONS', 'true').lower() == 'true',
            notification_quiet_start=os.getenv('NOTIFICATION_QUIET_START', '23:00'),
            notification_quiet_end=os.getenv('NOTIFICATION_QUIET_END', '07:00'),
        )


class NotificationBatcher:
    """Smart batching system for grouping similar notifications."""

    def __init__(self, batch_interval: int = 300):  # 5 minutes
        self.batch_interval = batch_interval
        self.batches = defaultdict(list)
        self.batch_timers = {}
        self.last_batch_sent = defaultdict(float)

    def add_to_batch(self, batch_type: str, notification_data: Dict[str, Any]):
        """Add notification to batch queue."""
        self.batches[batch_type].append({
            **notification_data,
            'timestamp': datetime.now()
        })

        # Start batch timer if not already running
        if batch_type not in self.batch_timers:
            self.batch_timers[batch_type] = asyncio.create_task(
                self._process_batch_after_delay(batch_type)
            )

    async def _process_batch_after_delay(self, batch_type: str):
        """Process batched notifications after delay."""
        await asyncio.sleep(self.batch_interval)

        if batch_type in self.batches and self.batches[batch_type]:
            batch_data = list(self.batches[batch_type])
            self.batches[batch_type].clear()

            # Generate batch summary
            summary = self._create_batch_summary(batch_type, batch_data)
            if summary:
                return summary

        # Clean up timer
        if batch_type in self.batch_timers:
            del self.batch_timers[batch_type]

        return None

    def _create_batch_summary(self, batch_type: str, batch_data: List[Dict]) -> Optional[Dict]:
        """Create summary message for batched notifications."""
        if not batch_data:
            return None

        count = len(batch_data)
        start_time = batch_data[0]['timestamp']
        end_time = batch_data[-1]['timestamp']
        duration = (end_time - start_time).total_seconds()

        if batch_type == 'profit':
            total_profit = sum(item.get('profit_usd', 0) for item in batch_data)
            pairs = list(set(item.get('token_pair', '') for item in batch_data))
            max_profit = max(item.get('profit_usd', 0) for item in batch_data)
            avg_profit = total_profit / count

            title = f"Trading Summary ({count} trades)"
            message = (
                f"**Total Profit:** ${total_profit:.2f}\n"
                f"**Average Profit:** ${avg_profit:.2f}\n"
                f"**Best Trade:** ${max_profit:.2f}\n"
                f"**Pairs Traded:** {', '.join(pairs[:3])}{'...' if len(pairs) > 3 else ''}\n"
                f"**Time Period:** {duration / 60:.0f} minutes"
            )

            return {
                'title': title,
                'message': message,
                'color': 0x00FF00,
                'type': 'batch_summary'
            }

        elif batch_type == 'opportunity':
            unique_pairs = list(set(item.get('token_pair', '') for item in batch_data))
            avg_profit = sum(item.get('profit_percent', 0) for item in batch_data) / count

            title = f"Opportunities Summary ({count} found)"
            message = (
                f"**Opportunities Found:** {count}\n"
                f"**Average Profit Potential:** {avg_profit:.2f}%\n"
                f"**Pairs:** {', '.join(unique_pairs[:3])}{'...' if len(unique_pairs) > 3 else ''}\n"
                f"**Time Period:** {duration / 60:.0f} minutes"
            )

            return {
                'title': title,
                'message': message,
                'color': 0xFFFF00,
                'type': 'batch_summary'
            }

        return None


class AlertRateLimiter:
    """Enhanced rate limiter with environment-aware controls."""

    def __init__(self, config: NotificationConfig):
        self.config = config
        self.max_per_hour = config.max_alerts_per_hour
        self.alerts_sent = []
        self.last_alert_times = {}
        self.rate_limited_until = 0

        # Minimum intervals between same type of alerts (seconds)
        self.min_intervals = {
            'profit': 60 if config.batch_notifications else 30,
            'opportunity': 120 if config.batch_notifications else 60,
            'error': 10,
            'status': 30,
            'batch_summary': 0,  # Always allow batch summaries
            'general': 15
        }

    def can_send_alert(self, alert_type: str = "general") -> bool:
        """Enhanced check with environment controls."""

        # Check dry run mode
        if self._is_dry_run() and not self.config.dry_run_notifications:
            logger.debug(f"Skipping {alert_type} notification - dry run mode")
            return False

        # Check quiet hours
        if self._is_quiet_hours():
            logger.debug(f"Skipping {alert_type} notification - quiet hours")
            return False

        # Allow critical messages
        if alert_type in ['error', 'batch_summary']:
            return True

        current_time = datetime.now().timestamp()

        # Check Discord rate limiting
        if current_time < self.rate_limited_until:
            logger.debug(f"Skipping {alert_type} alert - Discord rate limited")
            return False

        # Remove old alerts
        now = datetime.now()
        self.alerts_sent = [
            alert_time for alert_time in self.alerts_sent
            if (now - alert_time).total_seconds() < 3600
        ]

        # Check hourly limit
        if len(self.alerts_sent) >= self.max_per_hour:
            logger.debug(f"Hourly alert limit reached ({self.max_per_hour})")
            return False

        # Check minimum interval
        min_interval = self.min_intervals.get(alert_type, 15)
        last_alert_time = self.last_alert_times.get(alert_type, 0)

        if current_time - last_alert_time < min_interval:
            logger.debug(f"Skipping {alert_type} alert - too frequent")
            return False

        # Record alert
        self.alerts_sent.append(now)
        self.last_alert_times[alert_type] = current_time
        return True

    def _is_dry_run(self) -> bool:
        """Check if running in dry run mode."""
        return '--dry-run' in sys.argv or os.getenv('DRY_RUN_MODE', '').lower() == 'true'

    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        try:
            now = datetime.now().time()
            quiet_start = dt_time.fromisoformat(self.config.notification_quiet_start)
            quiet_end = dt_time.fromisoformat(self.config.notification_quiet_end)

            # Handle overnight quiet hours (e.g., 23:00 to 07:00)
            if quiet_start > quiet_end:
                return now >= quiet_start or now <= quiet_end
            else:
                return quiet_start <= now <= quiet_end
        except Exception as e:
            logger.debug(f"Error checking quiet hours: {e}")
            return False

    def set_rate_limited(self, retry_after: float = 60):
        """Set rate limit status."""
        self.rate_limited_until = datetime.now().timestamp() + retry_after
        logger.warning(f"Rate limited for {retry_after} seconds")

    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        return datetime.now().timestamp() < self.rate_limited_until


class NotificationManager:
    """Enhanced notification manager with smart controls."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        # Handle both NotificationConfig and MonitoringConfig (for backward compatibility)
        if config is None:
            self.config = NotificationConfig.from_env()
        elif hasattr(config, 'max_alerts_per_hour'):
            # It's already a NotificationConfig
            self.config = config
        else:
            # It's a MonitoringConfig, convert it to NotificationConfig
            self.config = self._convert_monitoring_config(config)

        self.rate_limiter = AlertRateLimiter(self.config)
        self.batcher = NotificationBatcher() if self.config.batch_notifications else None
        self.session = None

    def _convert_monitoring_config(self, monitoring_config):
        """Convert MonitoringConfig to NotificationConfig for compatibility."""
        return NotificationConfig(
            # Extract Discord settings
            discord_webhook_url=getattr(monitoring_config, 'discord_webhook_url', None),
            discord_username=getattr(monitoring_config, 'discord_username', 'Arbitrage Bot'),
            discord_avatar_url=getattr(monitoring_config, 'discord_avatar_url', None),

            # Extract Telegram settings
            telegram_bot_token=getattr(monitoring_config, 'telegram_bot_token', None),
            telegram_chat_id=getattr(monitoring_config, 'telegram_chat_id', None),

            # Set enhanced defaults
            max_alerts_per_hour=20,
            dry_run_notifications=os.getenv('DRY_RUN_NOTIFICATIONS', 'false').lower() == 'true',
            profit_notification_threshold=float(os.getenv('PROFIT_NOTIFICATION_THRESHOLD', '5.0')),
            batch_notifications=os.getenv('BATCH_NOTIFICATIONS', 'true').lower() == 'true',
            notification_quiet_start=os.getenv('NOTIFICATION_QUIET_START', '23:00'),
            notification_quiet_end=os.getenv('NOTIFICATION_QUIET_END', '07:00'),

            # Use monitoring config's notification settings if available
            enabled_channels=['discord', 'telegram'] if getattr(monitoring_config, 'enable_notifications', True) else []
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def send_profit_alert(
            self,
            token_pair: str,
            profit_percent: float,
            profit_amount: str,
            tx_hash: Optional[str] = None
    ):
        """Send profit alert with smart filtering."""

        if profit_percent < 0.0:
            return

        # Extract profit USD amount for threshold check
        profit_usd = self._extract_profit_usd(profit_amount)

        # Check profit threshold
        if profit_usd < self.config.profit_notification_threshold:
            logger.debug(f"Profit ${profit_usd:.2f} below threshold ${self.config.profit_notification_threshold}")
            return

        # Use batching if enabled
        if self.config.batch_notifications and self.batcher:
            self.batcher.add_to_batch('profit', {
                'token_pair': token_pair,
                'profit_percent': profit_percent,
                'profit_usd': profit_usd,
                'tx_hash': tx_hash
            })
            logger.debug(f"Added profit alert to batch: {token_pair} +${profit_usd:.2f}")
            return

        # Send individual notification
        if not self.rate_limiter.can_send_alert("profit"):
            return

        title = "Arbitrage Profit!"
        message = (
            f"**Token Pair:** {token_pair}\n"
            f"**Profit:** {profit_percent:.2f}%\n"
            f"**Amount:** {profit_amount}"
        )

        if tx_hash:
            message += f"\n**Transaction:** `{tx_hash}`"

        await self._send_to_all_channels(title, message, color=0x00FF00)

    async def send_opportunity_alert(
            self,
            token_pair: str,
            profit_percent: float,
            buy_exchange: str,
            sell_exchange: str,
            buy_price: float,
            sell_price: float
    ):
        """Send opportunity detection alert with batching."""

        if profit_percent < 0.0:
            return

        # Use batching if enabled
        if self.config.batch_notifications and self.batcher:
            self.batcher.add_to_batch('opportunity', {
                'token_pair': token_pair,
                'profit_percent': profit_percent,
                'buy_exchange': buy_exchange,
                'sell_exchange': sell_exchange
            })
            return

        if not self.rate_limiter.can_send_alert("opportunity"):
            return

        title = "Arbitrage Opportunity"
        message = (
            f"**Token Pair:** {token_pair}\n"
            f"**Potential Profit:** {profit_percent:.2f}%\n"
            f"**Buy from:** {buy_exchange} @ {buy_price:.6f}\n"
            f"**Sell to:** {sell_exchange} @ {sell_price:.6f}"
        )

        await self._send_to_all_channels(title, message, color=0xFFFF00)

    async def send_error_alert(
            self,
            error_message: str,
            tx_hash: Optional[str] = None,
            additional_info: Optional[str] = None
    ):
        """Send error alert (always sent, not batched)."""

        if not self.rate_limiter.can_send_alert("error"):
            return

        title = "Bot Error"
        message = f"**Error:** {error_message}"

        if tx_hash:
            message += f"\n**Transaction:** `{tx_hash}`"

        if additional_info:
            message += f"\n**Details:** {additional_info}"

        await self._send_to_all_channels(title, message, color=0xFF0000)

    async def send_status_alert(self, status: str, details: Optional[str] = None):
        """Send bot status update."""

        if not self.rate_limiter.can_send_alert("status"):
            return

        title = "Bot Status"
        message = f"**Status:** {status}"

        if details:
            message += f"\n**Details:** {details}"

        return await self._send_to_all_channels(title, message, color=0x0000FF)

    def _extract_profit_usd(self, profit_amount: str) -> float:
        """Extract USD profit amount from profit string."""
        try:
            # Handle formats like "$25.50", "25.50 MATIC", etc.
            import re
            # Look for dollar amounts first
            dollar_match = re.search(r'\$?(\d+\.?\d*)', profit_amount.replace(',', ''))
            if dollar_match:
                return float(dollar_match.group(1))
            return 0.0
        except:
            return 0.0

    async def _send_to_all_channels(self, title: str, message: str, color: int = 0x0080FF):
        """Send message to all enabled notification channels."""

        tasks = []

        if self.config.discord_webhook_url:
            tasks.append(self._send_discord(title, message, color))

        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            tasks.append(self._send_telegram(title, message))

        if tasks:
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return results
            except Exception as e:
                logger.error(f"Error sending notifications: {e}")

        return []

    async def _send_discord(self, title: str, message: str, color: int):
        """Send Discord webhook notification with enhanced rate limit handling."""

        try:
            if self.rate_limiter.is_rate_limited():
                logger.debug("Discord rate limited - skipping notification")
                return False

            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Flashloan Arbitrage Bot"
                }
            }

            payload = {
                "username": 'Flashloan Bot',
                "embeds": [embed]
            }

            if self.config.discord_avatar_url and self.config.discord_avatar_url.startswith(("http://", "https://")):
                payload["avatar_url"] = self.config.discord_avatar_url

            session = await self._get_session()
            async with session.post(
                    self.config.discord_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
            ) as response:

                if response.status == 204:
                    logger.debug("Discord notification sent successfully")
                    return True
                elif response.status == 429:
                    try:
                        response_data = await response.json()
                        retry_after = response_data.get('retry_after', 60)
                    except:
                        retry_after = 60

                    self.rate_limiter.set_rate_limited(retry_after)
                    return False
                else:
                    response_text = await response.text()
                    logger.error(f"Discord notification failed: {response.status} - {response_text}")
                    return False

        except Exception as e:
            logger.error(f"Discord notification error: {e}")
            return False

    async def _send_telegram(self, title: str, message: str):
        """Send Telegram bot message with rate limit handling."""

        try:
            full_message = f"*{title}*\n\n{message}"

            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": full_message,
                "parse_mode": "Markdown"
            }

            session = await self._get_session()
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    logger.debug("Telegram notification sent successfully")
                    return True
                elif response.status == 429:
                    try:
                        response_data = await response.json()
                        retry_after = response_data.get('parameters', {}).get('retry_after', 60)
                    except:
                        retry_after = 60

                    logger.warning(f"Telegram rate limited - retry after {retry_after}s")
                    return False
                else:
                    response_text = await response.text()
                    logger.error(f"Telegram notification failed: {response.status} - {response_text}")
                    return False

        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return False

    async def _send_slack(self, title: str, message: str):
        """Send Slack webhook notification."""

        try:
            payload = {
                "channel": self.config.slack_channel,
                "username": self.config.slack_username,
                "text": f"*{title}*\n{message}",
                "mrkdwn": True
            }

            session = await self._get_session()
            async with session.post(
                    self.config.slack_webhook_url,
                    json=payload,
                    timeout=10
            ) as response:
                if response.status == 200:
                    logger.debug("Slack notification sent successfully")
                    return True
                else:
                    logger.error(f"Slack notification failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            return False

    def _send_email(self, title: str, message: str):
        """Send email notification."""

        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from
            msg['Subject'] = title

            plain_message = message.replace("**", "").replace("*", "").replace("`", "")
            msg.attach(MIMEText(plain_message, 'plain'))

            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.starttls()
            server.login(self.config.smtp_username, self.config.smtp_password)

            for recipient in self.config.email_to:
                msg['To'] = recipient
                text = msg.as_string()
                server.sendmail(self.config.email_from, recipient, text)

            server.quit()
            logger.debug("Email notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False


# Global instance
_default_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the default notification manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = NotificationManager()
    return _default_manager


def setup_notifications(config: NotificationConfig):
    """Setup notifications with provided configuration."""
    global _default_manager
    _default_manager = NotificationManager(config)


# Convenience functions for backwards compatibility
async def send_discord_alert(
        webhook_url: str,
        title: str,
        message: str,
        color: int = 0x0080FF,
        username: str = "Arbitrage Bot"
):
    """Send standalone Discord alert."""

    try:
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {
            "username": username,
            "embeds": [embed]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=10) as response:
                return response.status == 204

    except Exception as e:
        logger.error(f"Discord alert error: {e}")
        return False


async def send_telegram_alert(
        bot_token: str,
        chat_id: str,
        title: str,
        message: str
):
    """Send standalone Telegram alert."""

    try:
        full_message = f"*{title}*\n\n{message}"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": full_message,
            "parse_mode": "Markdown"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                return response.status == 200

    except Exception as e:
        logger.error(f"Telegram alert error: {e}")
        return False


async def send_slack_alert(
        webhook_url: str,
        title: str,
        message: str,
        channel: str = "#trading"
):
    """Send standalone Slack alert."""

    try:
        payload = {
            "channel": channel,
            "text": f"*{title}*\n{message}",
            "mrkdwn": True
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=10) as response:
                return response.status == 200

    except Exception as e:
        logger.error(f"Slack alert error: {e}")
        return False


# Testing function
async def test_notifications(config: NotificationConfig):
    """Test all configured notification channels."""

    manager = NotificationManager(config)

    await manager.send_status_alert(
        "Test Alert",
        "This is a test message from the Enhanced Flashloan Arbitrage Bot notification system."
    )

    logger.info("Test notifications sent to all configured channels")
