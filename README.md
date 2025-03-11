# Bitfinex Funding Monitor

A Python bot that monitors your Bitfinex funding positions and sends notifications when lending status changes.

## Features

- Monitor all funds in your Bitfinex account
- Track lending status changes
- Send notifications through various channels (email, Telegram, etc.)
- Configurable monitoring frequency
- Detailed logging of status changes

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Bitfinex API credentials:
   ```
   BITFINEX_API_KEY=your_api_key
   BITFINEX_API_SECRET=your_api_secret
   ```
4. Configure notification settings in `config.py`
5. Run the bot:
   ```
   python main.py
   ```

## Configuration

You can configure the bot by editing the `config.py` file:

- Set the monitoring frequency
- Configure notification channels
- Customize notification messages
- Set specific funds to monitor (or monitor all)

## Notification Channels

The bot supports multiple notification channels:

- Email
- Telegram
- Discord
- Slack
- Desktop notifications

## Security Note

Your API keys are stored locally in the `.env` file. Never share this file or commit it to version control. The bot only requires read permissions on your Bitfinex account for monitoring purposes.

## License

MIT 