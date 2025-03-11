"""
Notification module for the Bitfinex Funding Monitor
"""

import os
import logging
import notifiers
from typing import Dict, Any, List, Optional

import config

# Configure logging
logger = logging.getLogger(__name__)

class NotificationManager:
    """Manages sending notifications through various channels"""
    
    def __init__(self):
        """Initialize the notification manager"""
        self.channels = {}
        self._setup_channels()
    
    def _setup_channels(self):
        """Set up notification channels based on configuration"""
        # Email notification
        if config.NOTIFICATION_CHANNELS.get('email', {}).get('enabled', False):
            email_config = config.NOTIFICATION_CHANNELS.get('email', {})
            self.channels['email'] = {
                'provider': notifiers.get_notifier('email'),
                'config': {
                    'to': email_config.get('to_email'),
                    'from': email_config.get('from_email'),
                    'host': email_config.get('smtp_server'),
                    'port': email_config.get('smtp_port'),
                    'username': email_config.get('smtp_username'),
                    'password': email_config.get('smtp_password'),
                    'tls': True,
                }
            }
            logger.info("Email notifications enabled")

        # Telegram notification
        if config.NOTIFICATION_CHANNELS.get('telegram', {}).get('enabled', False):
            telegram_config = config.NOTIFICATION_CHANNELS.get('telegram', {})
            self.channels['telegram'] = {
                'provider': notifiers.get_notifier('telegram'),
                'config': {
                    'token': telegram_config.get('bot_token'),
                    'chat_id': telegram_config.get('chat_id'),
                }
            }
            logger.info("Telegram notifications enabled")

        # Discord notification
        if config.NOTIFICATION_CHANNELS.get('discord', {}).get('enabled', False):
            discord_config = config.NOTIFICATION_CHANNELS.get('discord', {})
            self.channels['discord'] = {
                'provider': notifiers.get_notifier('discord'),
                'config': {
                    'webhook_url': discord_config.get('webhook_url'),
                }
            }
            logger.info("Discord notifications enabled")

        # Slack notification
        if config.NOTIFICATION_CHANNELS.get('slack', {}).get('enabled', False):
            slack_config = config.NOTIFICATION_CHANNELS.get('slack', {})
            self.channels['slack'] = {
                'provider': notifiers.get_notifier('slack'),
                'config': {
                    'webhook_url': slack_config.get('webhook_url'),
                }
            }
            logger.info("Slack notifications enabled")

        # Desktop notification
        if config.NOTIFICATION_CHANNELS.get('desktop', {}).get('enabled', False):
            try:
                # Test if desktop notifications are available on this system
                desktop_notifier = notifiers.get_notifier('desktop')
                test_result = desktop_notifier.notify(message="Test", title="Test")
                if test_result.status == "Success":
                    self.channels['desktop'] = {
                        'provider': desktop_notifier,
                        'config': {}
                    }
                    logger.info("Desktop notifications enabled")
                else:
                    logger.warning(f"Desktop notifications not working: {test_result.errors}")
            except Exception as e:
                logger.warning(f"Could not initialize desktop notifications: {e}")
    
    def send_notification(self, title: str, message: str, **kwargs) -> bool:
        """
        Send notification to all enabled channels
        
        Args:
            title: Notification title
            message: Notification message
            **kwargs: Additional parameters for notification formatting
        
        Returns:
            bool: True if notification sent successfully to at least one channel
        """
        successful = False
        
        for channel_name, channel_config in self.channels.items():
            try:
                provider = channel_config['provider']
                config_data = channel_config['config'].copy()
                
                # Handle channel-specific formatting
                if channel_name == 'email':
                    config_data['subject'] = title
                    config_data['message'] = message
                elif channel_name == 'desktop':
                    config_data['title'] = title
                    config_data['message'] = message
                elif channel_name in ['telegram', 'discord', 'slack']:
                    formatted_message = f"**{title}**\n{message}"
                    config_data['message'] = formatted_message
                
                # Send notification
                response = provider.notify(**config_data)
                
                if response.status == "Success":
                    logger.info(f"Notification sent via {channel_name}")
                    successful = True
                else:
                    logger.error(f"Failed to send {channel_name} notification: {response.errors}")
            
            except Exception as e:
                logger.error(f"Error sending {channel_name} notification: {e}")
        
        return successful
    
    def notify_lending_status_change(self, currency: str, old_status: Dict[str, Any], new_status: Dict[str, Any]) -> bool:
        """
        Send notification about lending status change
        
        Args:
            currency: Currency code
            old_status: Previous lending status
            new_status: New lending status
        
        Returns:
            bool: True if notification sent successfully
        """
        old_lending_status = old_status.get('lending_status')
        new_lending_status = new_status.get('lending_status')
        
        title = f"Bitfinex {currency} Lending Status Change"
        message = ""
        template_data = {
            'currency': currency,
        }
        
        # Determine the type of status change
        if old_lending_status == "inactive" and new_lending_status == "offered":
            message = f"{currency} funds are now offered for lending"
        
        elif old_lending_status == "offered" and new_lending_status == "active":
            template_data['rate'] = round(new_status.get('avg_loan_rate', 0), 2)
            message = config.NOTIFICATION_TEMPLATES.get('lending_active').format(**template_data)
        
        elif old_lending_status == "offered" and new_lending_status == "inactive":
            message = config.NOTIFICATION_TEMPLATES.get('lending_cancelled').format(**template_data)
        
        elif old_lending_status == "active" and new_lending_status == "inactive":
            message = config.NOTIFICATION_TEMPLATES.get('lending_closed').format(**template_data)
        
        elif old_lending_status == new_lending_status == "active":
            # Check for rate change
            old_rate = round(old_status.get('avg_loan_rate', 0), 2)
            new_rate = round(new_status.get('avg_loan_rate', 0), 2)
            
            if abs(old_rate - new_rate) > 0.01:  # Rate change threshold
                template_data['old_rate'] = old_rate
                template_data['new_rate'] = new_rate
                message = config.NOTIFICATION_TEMPLATES.get('rate_changed').format(**template_data)
            
            # Check for amount change
            old_amount = round(old_status.get('loaned_amount', 0), 8)
            new_amount = round(new_status.get('loaned_amount', 0), 8)
            
            if abs(old_amount - new_amount) > 0.0001:  # Amount change threshold
                template_data['old_amount'] = old_amount
                template_data['new_amount'] = new_amount
                
                # If we already have a rate change message, append to it
                if message:
                    message += f"\nAmount changed from {old_amount} to {new_amount} {currency}"
                else:
                    message = config.NOTIFICATION_TEMPLATES.get('amount_changed').format(**template_data)
        
        # If we have a message to send, send it
        if message:
            return self.send_notification(title, message)
        
        return False 