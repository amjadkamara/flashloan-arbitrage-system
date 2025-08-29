# bot/utils/notifications.py
"""
Notification system for the flashloan arbitrage bot.

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
from datetime import datetime
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
import asyncio
import aiohttp

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""

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

    # General settings
    enabled_channels: List[str] = None  # ["discord", "telegram", "slack", "email"]
    min_profit_alert: float = 1.0  # Minimum profit % for alerts
    max_alerts_per_hour: int = 10

    def __post_init__(self):
        if self.enabled_channels is None:
            self.enabled_channels = []
        if self.email_to is None:
            self.email_to = []


class AlertRateLimiter:
    """Rate limiter to prevent notification spam."""

    def __init__(self, max_per_hour: int = 10):
        self.max_per_hour = max_per_hour
        self.alerts_sent = []

    def can_send_alert(self, alert_type: str = "general") -> bool:
        """Check if we can send another alert."""
        now = datetime.now()

        # Remove alerts older than 1 hour
        self.alerts_sent = [
            alert_time for alert_time in self.alerts_sent
            if (now - alert_time).total_seconds() < 3600
        ]

        # Check if under limit
        if len(self.alerts_sent) >= self.max_per_hour:
            return False

        # Record this alert
        self.alerts_sent.append(now)
        return True


class NotificationManager:
    """Main notification manager for all alert types."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
        self.rate_limiter = AlertRateLimiter(10)
        self.session = None  # Will be initialized when needed

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
        """Send profit alert to all enabled channels."""

        if profit_percent < 0.0:
            return

        if not self.rate_limiter.can_send_alert("profit"):
            logger.warning("Profit alert rate limited")
            return

        title = "🎯 Arbitrage Profit!"
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
        """Send opportunity detection alert."""

        if profit_percent < 0.0:
            return

        if not self.rate_limiter.can_send_alert("opportunity"):
            return

        title = "👀 Arbitrage Opportunity"
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
        """Send error alert."""

        if not self.rate_limiter.can_send_alert("error"):
            return

        title = "❌ Bot Error"
        message = f"**Error:** {error_message}"

        if tx_hash:
            message += f"\n**Transaction:** `{tx_hash}`"

        if additional_info:
            message += f"\n**Details:** {additional_info}"

        await self._send_to_all_channels(title, message, color=0xFF0000)

    async def send_status_alert(self, status: str, details: Optional[str] = None):
        """Send bot status update."""

        title = "🤖 Bot Status"
        message = f"**Status:** {status}"

        if details:
            message += f"\n**Details:** {details}"

        return await self._send_to_all_channels(title, message, color=0x0000FF)
    async def _send_to_all_channels(self, title: str, message: str, color: int = 0x0080FF):
        """Send message to all enabled notification channels."""
        
        tasks = []
        results = []
        
        # Create tasks for each enabled channel
        if self.config.discord_webhook_url:
            tasks.append(self._send_discord(title, message, color))
        
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            tasks.append(self._send_telegram(title, message))
        
        # Run all tasks concurrently and collect results
        if tasks:
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error sending notifications: {e}")
                results = [e]
        
        return results
        return results

    async def _send_discord(self, title: str, message: str, color: int):
        """Send Discord webhook notification."""

        try:
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

            if self.config.discord_avatar_url:
                payload["avatar_url"] = self.config.discord_avatar_url

            session = await self._get_session()
            async with session.post(
                    self.config.discord_webhook_url,
                    json=payload,
                    timeout=10
            ) as response:
                if response.status == 204:
                    logger.debug("Discord notification sent successfully")
                    return True
                else:
                    logger.error(f"Discord notification failed: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Discord notification error: {e}")
            return False

    async def _send_telegram(self, title: str, message: str):
        """Send Telegram bot message."""

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
                else:
                    logger.error(f"Telegram notification failed: {response.status}")
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

            # Convert markdown-style formatting to plain text
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


# Convenience functions for direct usage
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
def test_notifications(config: NotificationConfig):
    """Test all configured notification channels."""

    manager = NotificationManager(config)

    manager.send_status_alert(
        "Test Alert",
        "This is a test message from the Flashloan Arbitrage Bot notification system."
    )

    logger.info("Test notifications sent to all configured channels")
