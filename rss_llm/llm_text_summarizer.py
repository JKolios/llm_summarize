import logging
import os
from html.parser import HTMLParser
from io import StringIO
from string import Template

import ollama
import requests
from openai import OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "NONE")

CLOUDFLARE_AI_API_BASE_URL = os.getenv("CLOUDFLARE_AI_API_BASE_URL", "NONE")
CLOUDFLARE_AI_API_KEY = os.getenv("CLOUDFLARE_AI_API_KEY", "NONE")
CLOUDFLARE_AI_GATEWAY_API_KEY = os.getenv("CLOUDFLARE_AI_GATEWAY_API_KEY", "NONE")

SYSTEM_PROMPT = """
"You are an assistant that specializes in summarising long texts.
Try to include the entirety of the text in the summary that you create.
"""


USER_PROMPT_TEMPLATE = Template(
    ' "Please return a summary of this text: $text_to_summarize"'
)


logger = logging.getLogger(__name__)


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
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.substitute(
                    text_to_summarize=strip_tags(text_to_summarize)
                ),
            },
        ]


class CloudflareAILLMTextSummarizer(LLMTextSummarizer):

    @staticmethod
    def _headers():
        return {
            "cf-aig-authorization": f"Bearer {CLOUDFLARE_AI_GATEWAY_API_KEY}",
            "Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}",
        }

    def summarize(self, text):
        model_input = {"messages": self._messages(text)}
        response = requests.post(
            f"{CLOUDFLARE_AI_API_BASE_URL}{self.model_name}",
            headers=self._headers(),
            json=model_input,
        )
        response.raise_for_status()
        response_content = response.json()
        return response_content["result"]["response"]


class OpenRouterLLMTextSummarizer(LLMTextSummarizer):
    def __init__(self, model_name):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        super().__init__(model_name)

    def summarize(self, text):
        # logger.info(f"{OPENROUTER_API_KEY}")
        completion = self.client.chat.completions.create(
            model=self.model_name, messages=self._messages(text)
        )

        return completion.choices[0].message.content


class OllamaLLMTextSummarizer(LLMTextSummarizer):

    def __init__(self, model_name, ollama_host="host.docker.internal"):
        self.client = ollama.Client(host=ollama_host)
        super().__init__(model_name)

    def summarize(self, text):
        response = self.client.chat(
            self.model_name,
            messages=self._messages(text),
        )

        return response.message.content
