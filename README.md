# RSS feed summary Telegram bot 


![Screenshot 2024-12-15 at 20 55 50](https://github.com/user-attachments/assets/40d2561c-9bca-4547-a38f-d21e18ce57a6)

A telegram bot that creates text and TTS summaries of RSS feed entries using LLMs.

## Usage

Create a local_dev.env file with these variables:

```shell
OPENAI_BASE_URL={The base URL of an OpenAI or compatible API}
OPENAI_API_KEY={As the name says, an OpenAI or compatible API key}

CLOUDFLARE_AI_API_BASE_URL={The base URL of a Cloudflare AI API, can be the URL of an AI Gateway}
CLOUDFLARE_AI_API_KEY={The API key of a Cloudflare AI API}
CLOUDFLARE_AI_GATEWAY_API_KEY={The API key of a Cloudflare AI Gateway}

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
* `/add_model` Add a new LLM, Usage: `/add_model <model_name> <model_provider_class, described below> <model_provider_identifier>`
* `/delete_model` Delete an LLM, Usage: `/delete_model <model_name>`


### Model provider classes

* `OpenAILLMTextSummarizer` : Uses an OpenAI or compatible API. This can also be used with llama.cpp for self-hosted models. Requires the `OPENAI_BASE_URL` and `OPENAI_API_KEY` env vars.
* `OllamaLLMTextSummarizer` : Uses an `ollama` API, most often for self-hosted models.
* `CloudflareAILLMTextSummarizer` : Uses the Cloudflare AI API through an AI Gateway: https://developers.cloudflare.com/ai-gateway/  Requires the `CLOUDFLARE_AI_API_BASE_URL`,`CLOUDFLARE_AI_API_KEY` and `CLOUDFLARE_AI_GATEWAY_API_KEY` env vars. 

### Possible TODOs

* Customizing the LLM prompts through the bot UI
* Returning the raw RSS entry for a specific summary
* Nicer config menu, maybe based on https://docs.python-telegram-bot.org/en/latest/examples.passportbot.html