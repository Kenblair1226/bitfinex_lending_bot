"""
Configuration settings for the Bitfinex Funding Monitor
"""

# Monitoring settings
MONITORING_INTERVAL_MINUTES = 30  # How often to check for status changes

# Funds to monitor (empty list means monitor all)
# Example: MONITORED_FUNDS = ["BTC", "ETH", "USD"]
MONITORED_FUNDS = []

# Notification settings
NOTIFICATION_CHANNELS = {
    "email": {
        "enabled": False,
        "to_email": "",  # Recipient email
        "from_email": "",  # Sender email
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
    },
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },
    "discord": {
        "enabled": False,
        "webhook_url": "",
    },
    "slack": {
        "enabled": False,
        "webhook_url": "",
    },
    "desktop": {
        "enabled": True,  # Desktop notifications enabled by default
    }
}

# Notification message templates
NOTIFICATION_TEMPLATES = {
    "lending_active": "{currency}: Lending activated at {rate}% APR",
    "lending_cancelled": "{currency}: Lending cancelled",
    "lending_closed": "{currency}: Lending closed, funds returned",
    "rate_changed": "{currency}: Rate changed from {old_rate}% to {new_rate}%",
    "amount_changed": "{currency}: Amount changed from {old_amount} to {new_amount}",
}

# Logging settings
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "bitfinex_monitor.log"

# Data storage settings
DATA_FILE = "funding_history.json"  # File to store historical data 