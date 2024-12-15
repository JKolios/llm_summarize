# RSS feed summary Telegram bot 


![Screenshot 2024-12-15 at 20 55 50](https://github.com/user-attachments/assets/40d2561c-9bca-4547-a38f-d21e18ce57a6)

Telegram bot that summarizes new content on select RSS feeds using LLMs and submits these summaries to a chat.

## Usage

Run the included Dockerfile as a docker container while providing it these environment variables:

```shell
MODEL_NAMES={Comma separated list of LLM model names, using OpenRouter semantics}
OPENROUTER_API_KEY={As the name says, an OpenRouter API key}
RSS_FEED_URLS={Comma separated list of LLM model names, using OpenRouter semantics}
TELEGRAM_BOT_TOKEN={A Telegram bot token, see https://core.telegram.org/bots/tutorial#obtain-your-bot-token}
TELEGRAM_CHAT_ID={A Telegram chat ID where the bot will send the RSS summaries}
```
