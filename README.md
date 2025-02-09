# RSS feed summary Telegram bot 


![Screenshot 2024-12-15 at 20 55 50](https://github.com/user-attachments/assets/40d2561c-9bca-4547-a38f-d21e18ce57a6)

Telegram bot that summarizes new content on select RSS feeds using LLMs and submits these summaries to a chat.

## Usage

Create a local_dev.env file with these variables:

```shell
CLOUDFLARE_AI_API_BASE_URL={The base URL of a Cloudflare AI API, can be the URL of an AI Gateway}
CLOUDFLARE_AI_API_KEY={The API key of a Cloudflare AI API}
CLOUDFLARE_AI_GATEWAY_API_KEY={The API key of a Cloudflare AI Gateway}
OPENROUTER_API_KEY={As the name says, an OpenRouter API key}
TELEGRAM_BOT_TOKEN={A Telegram bot token, see https://core.telegram.org/bots/tutorial#obtain-your-bot-token}
TELEGRAM_CHAT_ID={A Telegram chat ID where the bot will send the RSS summaries}
DB_CONNECTION_STRING={A sqlalchemy DB connection string, defaults to "postgresql+psycopg://postgres:postgres@postgres/llm_summarize"}
```

Run using `docker compose up`.

### Bot commands

* `/ping` ping the bot
* `/scan` scan for new RSS entries
* `/send` send all unsent RSS entries
* `/add_feed` Add a new RSS feed, Usage: `/add_feed <feed_name> <feed_url>`
* `/delete_feed` Delete an RSS feed, Usage: `/delete_feed <feed_name>`
* `/add_model` Add a new LLM, Usage: `/add_model <model_name> <model_provider_class> <model_provider_identifier>`
* `/delete_model` Delete an LLM, Usage: `/delete_model <model_name>`


### Possible TODOs

* Customizing the LLM prompts through the bot UI
* Returning the raw RSS entry for a specific summary
* Nicer config menu, maybe based on https://docs.python-telegram-bot.org/en/latest/examples.passportbot.html