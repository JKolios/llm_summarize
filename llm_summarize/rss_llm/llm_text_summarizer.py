import logging
import os
from html.parser import HTMLParser
from io import StringIO
from string import Template

import ollama
import aiohttp
from openai import AsyncOpenAI

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "NONE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "NONE")

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


class LLMSummarizer:
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


class CloudflareAISummarizer(LLMSummarizer):

    @staticmethod
    def _headers():
        return {
            "cf-aig-authorization": f"Bearer {CLOUDFLARE_AI_GATEWAY_API_KEY}",
            "Authorization": f"Bearer {CLOUDFLARE_AI_API_KEY}",
        }

    async def summarize(self, text):
        async with aiohttp.ClientSession() as session:
            model_input = {"messages": self._messages(text)}
            async with session.post(f"{CLOUDFLARE_AI_API_BASE_URL}{self.model_name}", headers=self._headers(), json=model_input) as response:
                response.raise_for_status()
                response_content = await response.json()
                return response_content["result"]["response"]


class OpenAISummarizer(LLMSummarizer):
    def __init__(self, model_name):
        self.client = AsyncOpenAI(
            base_url=OPENAI_BASE_URL,
            api_key=OPENAI_API_KEY,
        )
        super().__init__(model_name)

    async def summarize(self, text):
        completion = await self.client.chat.completions.create(
            model=self.model_name, messages=self._messages(text)
        )

        return  completion.choices[0].message.content


class OllamaSummarizer(LLMSummarizer):

    def __init__(self, model_name, ollama_host="host.docker.internal"):
        self.client = ollama.AsyncClient(host=ollama_host)
        super().__init__(model_name)

    async def summarize(self, text):
        response = await self.client.chat(
            self.model_name,
            messages=self._messages(text),
        )

        return response.message.content
