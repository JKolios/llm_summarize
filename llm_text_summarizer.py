import logging
import os
from string import Template
from io import StringIO
from html.parser import HTMLParser

import ollama
import requests
from openai import OpenAI
from pydantic import ValidationError

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "NONE")

CLOUDFLARE_AI_API_BASE_URL = os.getenv("CLOUDFLARE_AI_API_BASE_URL", "NONE")
CLOUDFLARE_AI_API_KEY = os.getenv("CLOUDFLARE_AI_API_KEY", "NONE")
CLOUDFLARE_AI_GATEWAY_API_KEY  = os.getenv("CLOUDFLARE_AI_GATEWAY_API_KEY", "NONE")

PROMPT_TEMPLATE = Template(
    ' "Please summarize this text in 5 sentences at maximum: $text_to_summarize"'
)


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


class LLMTextSummarizer:
    def __init__(self, model_name):
        self.model_name = model_name

    @staticmethod
    def _messages(text_to_summarize):
        return [
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.substitute(
                    text_to_summarize=strip_tags(text_to_summarize)
                ),
            }
        ]


class CloudflareAILLMTextSummarizer(LLMTextSummarizer):

    @staticmethod
    def _headers():
        return {
            "cf-aig-authorization": f"Bearer {CLOUDFLARE_AI_GATEWAY_API_KEY}",
            "Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}"}

    def summarize(self, text, summary_schema_class):
        model_input = {"messages": self._messages(text)}
        response = requests.post(
            f"{CLOUDFLARE_AI_API_BASE_URL}{self.model_name}",
            headers=self._headers(),
            json=model_input,
        )
        response.raise_for_status()
        response_content = response.json()
        summary = summary_schema_class(
            theme="", summary=response_content["result"]["response"]
        )
        return summary


class OpenRouterLLMTextSummarizer(LLMTextSummarizer):
    def __init__(self, model_name):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        super().__init__(model_name)

    def summarize(self, text, summary_schema_class):

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=self._messages(text),
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


class OllamaLLMTextSummarizer(LLMTextSummarizer):

    def summarize(self, text, summary_schema_class):

        response = ollama.chat(
            self.model_name,
            messages=self._messages(text),
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
