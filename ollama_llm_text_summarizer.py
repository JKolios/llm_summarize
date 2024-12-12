import ollama
from pydantic import ValidationError

class OllamaLLMTextSummarizer:
    def __init__(self, model_name):
        self.model_name = model_name

    def summarize(self, text, summary_schema_class):

        prompt = {"role": "user", "content": f"Please summarize this text in 5 sentences at maximum: {text}"}

        response = ollama.chat(
            self.model_name, messages=[prompt], format=summary_schema_class.model_json_schema()
        )

        print(response)
        try:
            text_summary = summary_schema_class.model_validate_json(
                response.message.content
            )
        except ValidationError as e:
            print(
                f"Response content does not match the expected schema: {response.content}"
            )
            raise e
        return text_summary