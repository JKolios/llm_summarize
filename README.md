# RSS feed summary Telegram bot 

Telegram bot that summarizes new content on select RSS feeds using LLMs.

## Usage

Run the included Dockerfile as a docker container while providing it these environment variables:

```shell
MODEL_NAMES={Comma separated list of LLM model names, using OpenRouter semantics}
OPENROUTER_API_KEY={As the name says, an OpenRouter API key}
RSS_FEED_URLS={Comma separated list of LLM model names, using OpenRouter semantics}
TELEGRAM_BOT_TOKEN={A Telegram bot token, see https://core.telegram.org/bots/tutorial#obtain-your-bot-token}
TELEGRAM_CHAT_ID={A Telegram chat ID where the bot will send the RSS summaries}
```
