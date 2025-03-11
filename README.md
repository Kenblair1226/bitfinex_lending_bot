# Bitfinex Funding Monitor Bot

A Telegram bot that monitors and manages Bitfinex funding positions.

## Prerequisites

- Docker
- Docker Compose

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd bitfinex_funding
```

2. Create your environment file:
```bash
cp .env.example .env
```

3. Edit the `.env` file with your credentials:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from [@BotFather](https://t.me/botfather)
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID
- `BITFINEX_API_KEY`: Your Bitfinex API key
- `BITFINEX_API_SECRET`: Your Bitfinex API secret

## Running the Bot

1. Build and start the container:
```bash
docker-compose up -d
```

2. View the logs:
```bash
docker-compose logs -f
```

3. Stop the bot:
```bash
docker-compose down
```

## Commands

- `/start` or `/help` - Show available commands
- `/status` - Show overall funding status
- `/status [currency]` - Show funding status for specific currency
- `/active` - Show active loans
- `/offered` - Show offered funds
- `/inactive` - Show inactive funds

## Development

To build the Docker image manually:
```bash
docker build -t bitfinex-funding-bot .
```

To run the container manually:
```bash
docker run --env-file .env bitfinex-funding-bot
```

## Logs

Logs are stored in the `./logs` directory and are persisted even if the container is removed.

## Security Notes

- Never commit your `.env` file
- Keep your API keys and secrets secure
- The bot only responds to messages from the configured chat ID 