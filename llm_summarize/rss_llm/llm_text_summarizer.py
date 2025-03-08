import logging
import os
from html.parser import HTMLParser
from io import StringIO
from string import Template
from typing import List, Tuple, Optional

import ollama
import aiohttp
from openai import AsyncOpenAI
import tiktoken
from tqdm import tqdm

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
            async with session.post(f"{CLOUDFLARE_AI_API_BASE_URL}{self.model_name}", headers=self._headers(),
                                    json=model_input) as response:
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

        return completion.choices[0].message.content


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


class OpenAISummarizerChunked(OpenAISummarizer):
    def __init__(self, model_name, detail=0.8):
        self.detail = detail
        # check detail is set correctly
        assert 0 <= self.detail <= 1
        super().__init__(model_name)

    def tokenize(self, text: str) -> List[str]:
        encoding = tiktoken.encoding_for_model(self.model_name.split('/')[-1])
        return encoding.encode(text)

    # This function chunks a text into smaller pieces based on a maximum token count and a delimiter.
    def chunk_on_delimiter(self, input_string: str,
                           max_tokens: int, delimiter: str) -> List[str]:
        chunks = input_string.split(delimiter)
        combined_chunks, _, dropped_chunk_count = self.combine_chunks_with_no_minimum(
            chunks, max_tokens, chunk_delimiter=delimiter, add_ellipsis_for_overflow=True
        )
        if dropped_chunk_count > 0:
            print(f"warning: {dropped_chunk_count} chunks were dropped due to overflow")
        combined_chunks = [f"{chunk}{delimiter}" for chunk in combined_chunks]
        return combined_chunks

    # This function combines text chunks into larger blocks without exceeding a specified token count. It returns the combined text blocks, their original indices, and the count of chunks dropped due to overflow.
    def combine_chunks_with_no_minimum(
            self,
            chunks: List[str],
            max_tokens: int,
            chunk_delimiter="\n\n",
            header: Optional[str] = None,
            add_ellipsis_for_overflow=False,
    ) -> Tuple[List[str], List[int]]:
        dropped_chunk_count = 0
        output = []  # list to hold the final combined chunks
        output_indices = []  # list to hold the indices of the final combined chunks
        candidate = (
            [] if header is None else [header]
        )  # list to hold the current combined chunk candidate
        candidate_indices = []
        for chunk_i, chunk in enumerate(chunks):
            chunk_with_header = [chunk] if header is None else [header, chunk]
            if len(self.tokenize(chunk_delimiter.join(chunk_with_header))) > max_tokens:
                print(f"warning: chunk overflow")
                if (
                        add_ellipsis_for_overflow
                        and len(self.tokenize(chunk_delimiter.join(candidate + ["..."]))) <= max_tokens
                ):
                    candidate.append("...")
                    dropped_chunk_count += 1
                continue  # this case would break downstream assumptions
            # estimate token count with the current chunk added
            extended_candidate_token_count = len(self.tokenize(chunk_delimiter.join(candidate + [chunk])))
            # If the token count exceeds max_tokens, add the current candidate to output and start a new candidate
            if extended_candidate_token_count > max_tokens:
                output.append(chunk_delimiter.join(candidate))
                output_indices.append(candidate_indices)
                candidate = chunk_with_header  # re-initialize candidate
                candidate_indices = [chunk_i]
            # otherwise keep extending the candidate
            else:
                candidate.append(chunk)
                candidate_indices.append(chunk_i)
        # add the remaining candidate to output if it's not empty
        if (header is not None and len(candidate) > 1) or (header is None and len(candidate) > 0):
            output.append(chunk_delimiter.join(candidate))
            output_indices.append(candidate_indices)
        return output, output_indices, dropped_chunk_count

    async def summarize(self, text: str,
                  minimum_chunk_size: Optional[int] = 500,
                  chunk_delimiter: str = ".",
                  summarize_recursively=False):
        """
        Summarizes a given text by splitting it into chunks, each of which is summarized individually.
        The level of detail in the summary can be adjusted, and the process can optionally be made recursive.

        Parameters:
        - text (str): The text to be summarized.
        - detail (float, optional): A value between 0 and 1 indicating the desired level of detail in the summary.
          0 leads to a higher level summary, and 1 results in a more detailed summary. Defaults to 0.
        - model (str, optional): The model to use for generating summaries. Defaults to 'gpt-3.5-turbo'.
        - additional_instructions (Optional[str], optional): Additional instructions to provide to the model for customizing summaries.
        - minimum_chunk_size (Optional[int], optional): The minimum size for text chunks. Defaults to 500.
        - chunk_delimiter (str, optional): The delimiter used to split the text into chunks. Defaults to ".".
        - summarize_recursively (bool, optional): If True, summaries are generated recursively, using previous summaries for context.
        - verbose (bool, optional): If True, prints detailed information about the chunking process.

        Returns:
        - str: The final compiled summary of the text.

        The function first determines the number of chunks by interpolating between a minimum and a maximum chunk count based on the `detail` parameter.
        It then splits the text into chunks and summarizes each chunk. If `summarize_recursively` is True, each summary is based on the previous summaries,
        adding more context to the summarization process. The function returns a compiled summary of all chunks.
        """


        # interpolate the number of chunks based to get specified level of detail
        max_chunks = len(self.chunk_on_delimiter(text, minimum_chunk_size, chunk_delimiter))
        min_chunks = 1
        num_chunks = int(min_chunks + self.detail * (max_chunks - min_chunks))

        # adjust chunk_size based on interpolated number of chunks
        document_length = len(self.tokenize(text))
        chunk_size = max(minimum_chunk_size, document_length // num_chunks)
        text_chunks = self.chunk_on_delimiter(text, chunk_size, chunk_delimiter)

        logger.info(f"Splitting the text into {len(text_chunks)} chunks to be summarized.")
        logger.info(f"Chunk lengths are {[len(self.tokenize(x)) for x in text_chunks]}")

        # set system message
        system_message_content = "Rewrite this text in summarized form."


        accumulated_summaries = []
        for chunk in tqdm(text_chunks):
            if summarize_recursively and accumulated_summaries:
                # Creating a structured prompt for recursive summarization
                accumulated_summaries_string = '\n\n'.join(accumulated_summaries)
                user_message_content = f"Previous summaries:\n\n{accumulated_summaries_string}\n\nText to summarize next:\n\n{chunk}"
            else:
                # Directly passing the chunk for summarization without recursive context
                user_message_content = chunk

            # Constructing messages based on whether recursive summarization is applied
            messages = [
                {"role": "system", "content": system_message_content},
                {"role": "user", "content": user_message_content}
            ]

            # Assuming this function gets the completion and works as expected
            completion = await self.client.chat.completions.create(
                model=self.model_name, messages=self._messages(text)
            )

            response = completion.choices[0].message.content
            accumulated_summaries.append(response)

        # Compile final summary from partial summaries
        final_summary = '\n\n'.join(accumulated_summaries)

        return final_summary
