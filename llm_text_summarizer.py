import logging
import os
from string import Template

import ollama
import requests
from openai import OpenAI
from pydantic import ValidationError

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "NONE")

CLOUDFLARE_AI_API_BASE_URL = os.getenv("CLOUDFLARE_AI_API_BASE_URL", "NONE")
CLOUDFLARE_AI_API_KEY = os.getenv("CLOUDFLARE_AI_API_KEY", "NONE")

PROMPT_TEMPLATE = Template(
    ' "Please summarize this text in 5 sentences at maximum: $text_to_summarize"'
)


class CloudflareAILLMTextSummarizer:
    def __init__(self, model_name):
        self.model_name = model_name

    @staticmethod
    def _headers():
        return {"Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}"}

    @staticmethod
    def _messages(text_to_summarize):
        return [
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.substitute(
                    text_to_summarize=text_to_summarize
                ),
            }
        ]

    def summarize(self, text, summary_schema_class):
        model_input = {"messages": self._messages(text)}
        response = requests.post(
            f"{CLOUDFLARE_AI_API_BASE_URL}{self.model_name}",
            headers=self._headers(),
            json=model_input,
        )
        response_content = response.json()
        summary = summary_schema_class(
            theme="", summary=response_content["result"]["response"]
        )
        return summary


class OpenRouterLLMTextSummarizer:
    def __init__(self, model_name):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        self.model_name = model_name

    def summarize(self, text, summary_schema_class):

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": PROMPT_TEMPLATE.substitute(text_to_summarize=text),
                }
            ],
            response_format=summary_schema_class,
        )

        try:
            text_summary = summary_schema_class.model_validate(
                completion.choices[0].message.parsed
            )
        except ValidationError as e:
            logging.error(
                f"Response content does not match the expected schema: {completion.choices[0].message.parsed}"
            )
            raise e
        return text_summary


class OllamaLLMTextSummarizer:
    def __init__(self, model_name):
        self.model_name = model_name

    def summarize(self, text, summary_schema_class):

        response = ollama.chat(
            self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": PROMPT_TEMPLATE.substitute(text_to_summarize=text),
                }
            ],
            format=summary_schema_class.model_json_schema(),
        )

        try:
            text_summary = summary_schema_class.model_validate_json(
                response.message.content
            )
        except ValidationError as e:
            logging.error(
                f"Response content does not match the expected schema: {response.content}"
            )
            raise e
        return text_summary
