import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config/.env')

print("� Checking Discord configuration...")
print("=" * 50)

# Check Discord settings
discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
discord_username = os.getenv('DISCORD_USERNAME')

print(f"DISCORD_WEBHOOK_URL: {'✅ Set' if discord_webhook else '❌ Not set'}")
print(f"DISCORD_USERNAME: {'✅ Set' if discord_username else '❌ Not set'}")

if discord_webhook:
    print(f"Webhook URL: {discord_webhook[:30]}...")  # Show first 30 chars for security

# Check if settings.py has the attribute
try:
    from config.settings import settings
    print(f"\n� Settings class check:")
    print(f"Has discord_webhook_url: {'✅ Yes' hasattr(settings, 'discord_webhook_url') else '❌ No'}")
    
    if hasattr(settings, 'discord_webhook_url'):
        print(f"Current value: {settings.discord_webhook_url}")
        
except Exception as e:
    print(f"❌ Error loading settings: {e}")

print("\n" + "=" * 50)
print("� If Discord settings are not in config/settings.py, you need to add:")
print("""
# In config/settings.py, add to Settings class:
discord_webhook_url: str = Field(None, env='DISCORD_WEBHOOK_URL')
discord_username: str = Field('Flashloan Bot', env='DISCORD_USERNAME')
""")
