"""
Telegram bot for the Bitfinex Funding Monitor
"""

import os
import logging
import threading
import time
from typing import Dict, Any, Optional
import telebot
from dotenv import load_dotenv

from bitfinex_api import BitfinexAPI

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class TelegramBot:
    """Handles Telegram bot commands for the Bitfinex Funding Monitor"""
    
    def __init__(self, bitfinex_api: BitfinexAPI):
        """
        Initialize the Telegram bot
        
        Args:
            bitfinex_api: BitfinexAPI instance to get data from
        """
        self.bitfinex = bitfinex_api
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.bot = None
        self.is_running = False
        self.should_stop = False
        self.reconnect_delay = 1  # Initial delay in seconds
        self.max_reconnect_delay = 300  # Maximum delay of 5 minutes
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot token or chat ID not set in .env file. Telegram bot commands will not be available.")
            return
        
        try:
            self.bot = telebot.TeleBot(self.bot_token)
            self._setup_commands()
            logger.info("Telegram bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
    
    def _setup_commands(self):
        """Set up command handlers for the Telegram bot"""
        if not self.bot:
            return
        
        @self.bot.message_handler(commands=['start', 'help'])
        def handle_start_help(message):
            if str(message.chat.id) != self.chat_id:
                self.bot.reply_to(message, "Unauthorized access denied.")
                logger.warning(f"Unauthorized access attempt from chat ID: {message.chat.id}")
                return
                
            help_text = (
                "Bitfinex Funding Monitor Bot\n\n"
                "Available commands:\n"
                "/status - Show overall funding status\n"
                "/status [currency] - Show funding status for specific currency\n"
                "/active - Show active loans\n"
                "/offered - Show offered funds\n"
                "/inactive - Show inactive funds\n"
                "/help - Show this help message"
            )
            self.bot.reply_to(message, help_text)
        
        @self.bot.message_handler(commands=['status'])
        def handle_status(message):
            if str(message.chat.id) != self.chat_id:
                self.bot.reply_to(message, "Unauthorized access denied.")
                return
                
            try:
                # Check if specific currency was requested
                command_args = message.text.split()
                if len(command_args) > 1:
                    currency = command_args[1].upper()
                    self._send_currency_status(message.chat.id, currency)
                else:
                    self._send_overall_status(message.chat.id)
            except Exception as e:
                error_msg = f"Error getting funding status: {e}"
                logger.error(error_msg)
                self.bot.send_message(message.chat.id, error_msg)
        
        @self.bot.message_handler(commands=['active'])
        def handle_active(message):
            if str(message.chat.id) != self.chat_id:
                self.bot.reply_to(message, "Unauthorized access denied.")
                return
                
            try:
                self._send_filtered_status(message.chat.id, "active")
            except Exception as e:
                error_msg = f"Error getting active loans: {e}"
                logger.error(error_msg)
                self.bot.send_message(message.chat.id, error_msg)
        
        @self.bot.message_handler(commands=['offered'])
        def handle_offered(message):
            if str(message.chat.id) != self.chat_id:
                self.bot.reply_to(message, "Unauthorized access denied.")
                return
                
            try:
                self._send_filtered_status(message.chat.id, "offered")
            except Exception as e:
                error_msg = f"Error getting offered funds: {e}"
                logger.error(error_msg)
                self.bot.send_message(message.chat.id, error_msg)
        
        @self.bot.message_handler(commands=['inactive'])
        def handle_inactive(message):
            if str(message.chat.id) != self.chat_id:
                self.bot.reply_to(message, "Unauthorized access denied.")
                return
                
            try:
                self._send_filtered_status(message.chat.id, "inactive")
            except Exception as e:
                error_msg = f"Error getting inactive funds: {e}"
                logger.error(error_msg)
                self.bot.send_message(message.chat.id, error_msg)
    
    def _send_overall_status(self, chat_id):
        """Send overall funding status"""
        funding_status = self.bitfinex.get_funding_status()
        
        if not funding_status:
            self.bot.send_message(chat_id, "No funding data available.")
            return
        
        # Prepare summary message - count individual offers/loans, not just currencies
        active_loans = sum(len(s.get('loans', [])) for s in funding_status.values())
        offered = sum(len(s.get('offers', [])) for s in funding_status.values())
        inactive = sum(1 for s in funding_status.values() if s.get('lending_status') == 'inactive')
        
        # Get the correct totals from the API's calculation
        total_funds = sum(s.get('total_balance', 0) for s in funding_status.values())
        loaned_funds = sum(s.get('loaned_amount', 0) for s in funding_status.values())
        offered_funds = sum(s.get('offered_amount', 0) for s in funding_status.values())
        wallet_funds = sum(s.get('wallet_balance', 0) for s in funding_status.values())
        
        message = (
            "📊 *Bitfinex Funding Status*\n\n"
            f"*Summary:*\n"
            f"Active Loans: {active_loans}\n"
            f"Offered: {offered}\n"
            f"Inactive: {inactive}\n\n"
            f"*Balances:*\n"
            f"Total Funds: {total_funds:.2f}\n"  # Now wallet + loaned, not including offered
            f"Loaned: {loaned_funds:.2f}\n"
            f"Offered: {offered_funds:.2f}\n"
            f"In Wallet: {wallet_funds:.2f}\n\n"
            "Use /status [currency] for details on specific currency"
        )
        
        self.bot.send_message(chat_id, message, parse_mode="Markdown")
    
    def _send_currency_status(self, chat_id, currency):
        """Send funding status for specific currency"""
        funding_status = self.bitfinex.get_funding_status()
        
        if not funding_status or currency not in funding_status:
            self.bot.send_message(chat_id, f"No data available for {currency}")
            return
        
        status = funding_status[currency]
        lending_status = status.get('lending_status', 'unknown')
        
        # Format status emoji based on lending status
        status_emoji = "🔴"  # inactive
        if lending_status == "active":
            status_emoji = "🟢"
        elif lending_status == "offered":
            status_emoji = "🟡"
        
        # Prepare message with 2 decimal places
        message = (
            f"📊 *{currency} Funding Status* {status_emoji}\n\n"
            f"*Status:* {lending_status.capitalize()}\n\n"
            f"*Balances:*\n"
            f"Total: {status.get('total_balance', 0):.2f} {currency}\n"
            f"In Wallet: {status.get('wallet_balance', 0):.2f} {currency}\n"
            f"Offered: {status.get('offered_amount', 0):.2f} {currency}\n"
            f"Loaned: {status.get('loaned_amount', 0):.2f} {currency}\n\n"
        )
        
        # Add detailed transaction information
        if lending_status == "active":
            message += f"*Active Loans:*\n"
            loans = status.get('loans', [])
            
            if loans:
                for i, loan in enumerate(loans, 1):
                    amount = loan.get('amount', 0)
                    rate = loan.get('rate', 0)
                    period = loan.get('period', 0)
                    period_display = period if period > 0 else "Unknown"
                    created_time = loan.get('created_at', 0)
                    
                    # Format creation time if available
                    if created_time:
                        try:
                            # Convert Unix timestamp to human-readable date
                            from datetime import datetime
                            date_str = datetime.fromtimestamp(created_time/1000).strftime('%Y-%m-%d %H:%M')
                            message += f"{i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days) - {date_str}\n"
                        except (ValueError, TypeError):
                            message += f"{i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days)\n"
                    else:
                        message += f"{i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days)\n"
            else:
                message += "No individual loan data available\n"
            
            message += "\n"
        
        if lending_status == "offered":
            message += f"*Active Offers:*\n"
            offers = status.get('offers', [])
            
            if offers:
                for i, offer in enumerate(offers, 1):
                    amount = offer.get('amount', 0)
                    rate = offer.get('rate', 0)
                    period = offer.get('period', 0)
                    period_display = period if period > 0 else "Unknown"
                    created_time = offer.get('created_at', 0)
                    
                    # Format creation time if available
                    if created_time:
                        try:
                            # Convert Unix timestamp to human-readable date
                            from datetime import datetime
                            date_str = datetime.fromtimestamp(created_time/1000).strftime('%Y-%m-%d %H:%M')
                            message += f"{i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days) - {date_str}\n"
                        except (ValueError, TypeError):
                            message += f"{i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days)\n"
                    else:
                        message += f"{i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days)\n"
            else:
                message += "No individual offer data available\n"
        
        # Truncate message if too long (Telegram has a 4096 character limit)
        if len(message) > 4000:
            message = message[:3950] + "...\n\n(Message truncated due to length)"
            
        self.bot.send_message(chat_id, message, parse_mode="Markdown")
    
    def _send_filtered_status(self, chat_id, status_filter):
        """Send filtered funding status based on lending status"""
        funding_status = self.bitfinex.get_funding_status()
        
        if not funding_status:
            self.bot.send_message(chat_id, "No funding data available.")
            return
        
        # Filter currencies by status
        filtered_currencies = {
            curr: data for curr, data in funding_status.items() 
            if data.get('lending_status') == status_filter
        }
        
        if not filtered_currencies:
            self.bot.send_message(chat_id, f"No {status_filter} funding positions found.")
            return
        
        # Prepare status message
        if status_filter == "active":
            emoji = "🟢"
            title = f"{emoji} *Active Loans*\n\n"
        elif status_filter == "offered":
            emoji = "🟡" 
            title = f"{emoji} *Offered Funds*\n\n"
        else:
            emoji = "🔴"
            title = f"{emoji} *Inactive Funds*\n\n"
        
        message = title
        
        # Add details for each currency including individual transactions
        for currency, data in filtered_currencies.items():
            message += f"*{currency}*:\n"
            
            if status_filter == "active":
                loans = data.get('loans', [])
                if loans:
                    for i, loan in enumerate(loans, 1):
                        amount = loan.get('amount', 0)
                        rate = loan.get('rate', 0)
                        
                        # Check for period data and its type
                        period = loan.get('period', 0)
                        # Debug: Add the actual raw data if period is 0
                        period_display = period if period > 0 else "Unknown"
                        
                        # Use 2 decimal places instead of 8
                        message += f"  {i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days)\n"
                else:
                    message += f"  No individual loan data available\n"
                    
            elif status_filter == "offered":
                offers = data.get('offers', [])
                if offers:
                    for i, offer in enumerate(offers, 1):
                        amount = offer.get('amount', 0)
                        rate = offer.get('rate', 0)
                        
                        # Check for period data and its type
                        period = offer.get('period', 0)
                        # Debug: Add the actual raw data if period is 0
                        period_display = period if period > 0 else "Unknown"
                        
                        # Use 2 decimal places instead of 8
                        message += f"  {i}. {amount:.2f} @ {rate:.2f}% APR ({period_display} days)\n"
                else:
                    message += f"  No individual offer data available\n"
                    
            else:  # inactive funds just have wallet balance
                wallet_balance = data.get('wallet_balance', 0)
                # Use 2 decimal places instead of 8
                message += f"  {wallet_balance:.2f} in wallet\n"
            
            message += "\n"  # Add extra line between currencies
        
        # Truncate message if too long (Telegram has a 4096 character limit)
        if len(message) > 4000:
            message = message[:3950] + "...\n\n(Message truncated due to length)"
            
        self.bot.send_message(chat_id, message, parse_mode="Markdown")
    
    def start(self):
        """Start the Telegram bot in a separate thread"""
        if not self.bot:
            logger.warning("Telegram bot not initialized, commands will not be available")
            return
        
        if self.is_running:
            logger.warning("Telegram bot is already running")
            return
        
        self.is_running = True
        self.should_stop = False
        self.reconnect_delay = 1  # Reset reconnect delay
        
        def run_bot():
            logger.info("Starting Telegram bot polling")
            while not self.should_stop:
                try:
                    # Try to send startup message
                    if not hasattr(self, 'startup_message_sent'):
                        try:
                            startup_message = "🤖 Bitfinex Funding Monitor Bot is now online!\nSend /help for available commands."
                            self.bot.send_message(self.chat_id, startup_message)
                            self.startup_message_sent = True
                        except Exception as e:
                            logger.error(f"Failed to send startup message: {e}")
                    
                    # Start polling
                    self.bot.infinity_polling(timeout=60, long_polling_timeout=30)
                except Exception as e:
                    if self.should_stop:
                        break
                        
                    logger.error(f"Telegram bot polling error: {e}")
                    logger.info(f"Attempting to reconnect in {self.reconnect_delay} seconds...")
                    
                    # Wait before reconnecting
                    time.sleep(self.reconnect_delay)
                    
                    # Exponential backoff with maximum delay
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                    
                    # Try to recreate the bot instance
                    try:
                        self.bot = telebot.TeleBot(self.bot_token)
                        self._setup_commands()
                        logger.info("Successfully recreated Telegram bot instance")
                        self.reconnect_delay = 1  # Reset delay after successful reconnection
                    except Exception as e:
                        logger.error(f"Failed to recreate Telegram bot instance: {e}")
                        continue
            
            self.is_running = False
            logger.info("Telegram bot polling stopped")
        
        # Start the bot in a separate thread
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
    
    def stop(self):
        """Stop the Telegram bot"""
        if not self.is_running:
            return
            
        logger.info("Stopping Telegram bot")
        self.should_stop = True
        
        try:
            # Try to send shutdown message
            shutdown_message = "🔌 Bitfinex Funding Monitor Bot is going offline. Goodbye!"
            self.bot.send_message(self.chat_id, shutdown_message)
        except Exception as e:
            logger.error(f"Failed to send shutdown message: {e}")
        
        # Stop the polling
        try:
            self.bot.stop_polling()
        except Exception as e:
            logger.error(f"Error stopping bot polling: {e}")
        
        # Wait for the thread to finish
        if hasattr(self, 'bot_thread'):
            self.bot_thread.join(timeout=5)
            
        self.is_running = False 