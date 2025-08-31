import os
from dotenv import load_dotenv
load_dotenv('config/.env')

print("Testing Discord configuration...")
print("DISCORD_WEBHOOK_URL exists:", bool(os.getenv('DISCORD_WEBHOOK_URL')))
print("DISCORD_USERNAME exists:", bool(os.getenv('DISCORD_USERNAME')))

# Test basic import
try:
    from bot.utils.notifications import NotificationManager, NotificationConfig
    print("✅ Notification imports work")
except Exception as e:
    print("❌ Notification import failed:", e)
