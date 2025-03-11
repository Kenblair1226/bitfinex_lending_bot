"""
Main monitoring module for the Bitfinex Funding Monitor
"""

import os
import sys
import time
import json
import logging
import schedule
from typing import Dict, Any, List, Optional
from datetime import datetime

import config
from bitfinex_api import BitfinexAPI
from notifications import NotificationManager
from telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class FundingMonitor:
    """Main class for monitoring Bitfinex funding status"""
    
    def __init__(self):
        """Initialize the funding monitor"""
        self.bitfinex = BitfinexAPI()
        self.notifier = NotificationManager()
        self.telegram_bot = None
        self.previous_status = {}
        self.load_previous_status()
        
        # Initialize Telegram bot if credentials are available
        if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
            self.telegram_bot = TelegramBot(self.bitfinex)
        
    def load_previous_status(self):
        """Load previous funding status from JSON file"""
        try:
            if os.path.exists(config.DATA_FILE):
                with open(config.DATA_FILE, 'r') as f:
                    self.previous_status = json.load(f)
                logger.info(f"Loaded previous funding status from {config.DATA_FILE}")
            else:
                logger.info(f"No previous funding status found, will create new one")
        except Exception as e:
            logger.error(f"Error loading previous funding status: {e}")
    
    def save_current_status(self, current_status):
        """Save current funding status to JSON file"""
        try:
            with open(config.DATA_FILE, 'w') as f:
                json.dump(current_status, f, indent=2)
            logger.info(f"Saved current funding status to {config.DATA_FILE}")
        except Exception as e:
            logger.error(f"Error saving current funding status: {e}")
    
    def check_for_changes(self):
        """Check for changes in funding status and send notifications"""
        try:
            # Get current funding status
            current_status = self.bitfinex.get_funding_status()
            
            if not current_status:
                logger.warning("Failed to get current funding status")
                return
            
            # Filter currencies if configured
            monitored_currencies = config.MONITORED_FUNDS
            if monitored_currencies:
                current_status = {k: v for k, v in current_status.items() if k in monitored_currencies}
            
            # Check for changes and send notifications
            for currency, status in current_status.items():
                previous = self.previous_status.get(currency, {
                    'lending_status': 'unknown',
                    'wallet_balance': 0.0,
                    'offered_amount': 0.0,
                    'loaned_amount': 0.0,
                    'avg_offer_rate': 0.0,
                    'avg_loan_rate': 0.0,
                })
                
                if previous.get('lending_status') == 'unknown':
                    # First time seeing this currency, just log it
                    logger.info(f"First status for {currency}: {status['lending_status']}")
                    continue
                
                # Check if lending status has changed
                if previous.get('lending_status') != status.get('lending_status'):
                    logger.info(f"{currency} lending status changed: {previous.get('lending_status')} -> {status.get('lending_status')}")
                    self.notifier.notify_lending_status_change(currency, previous, status)
                    continue
                
                # Check for rate or amount changes if active
                if status.get('lending_status') == 'active':
                    old_rate = round(previous.get('avg_loan_rate', 0), 2)
                    new_rate = round(status.get('avg_loan_rate', 0), 2)
                    
                    old_amount = round(previous.get('loaned_amount', 0), 8)
                    new_amount = round(status.get('loaned_amount', 0), 8)
                    
                    rate_changed = abs(old_rate - new_rate) > 0.01
                    amount_changed = abs(old_amount - new_amount) > 0.0001
                    
                    if rate_changed or amount_changed:
                        logger.info(f"{currency} lending parameters changed")
                        self.notifier.notify_lending_status_change(currency, previous, status)
            
            # Save current status for next comparison
            self.previous_status = current_status
            self.save_current_status(current_status)
            
            # Log a summary
            active_loans = sum(1 for s in current_status.values() if s.get('lending_status') == 'active')
            offered = sum(1 for s in current_status.values() if s.get('lending_status') == 'offered')
            inactive = sum(1 for s in current_status.values() if s.get('lending_status') == 'inactive')
            
            logger.info(f"Status check complete. Active: {active_loans}, Offered: {offered}, Inactive: {inactive}")
            
        except Exception as e:
            logger.error(f"Error checking for funding status changes: {e}")
    
    def run(self):
        """Run the funding monitor"""
        # Initial check
        logger.info("Starting Bitfinex Funding Monitor")
        self.check_for_changes()
        
        # Start Telegram bot if available
        if self.telegram_bot:
            self.telegram_bot.start()
            logger.info("Telegram bot started - you can now send commands to check funding status")
        
        # Schedule regular checks
        interval_minutes = config.MONITORING_INTERVAL_MINUTES
        logger.info(f"Scheduling checks every {interval_minutes} minutes")
        
        schedule.every(interval_minutes).minutes.do(self.check_for_changes)
        
        # Run the scheduler
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            if self.telegram_bot and self.telegram_bot.is_running:
                self.telegram_bot.stop()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if self.telegram_bot and self.telegram_bot.is_running:
                self.telegram_bot.stop()
            raise

def main():
    """Main function"""
    monitor = FundingMonitor()
    monitor.run()

if __name__ == "__main__":
    main() 