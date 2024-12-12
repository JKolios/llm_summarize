from sqlite_connection import SQLiteConnection
from rss_summarizer import RSSSummarizer
from ollama_llm_text_summarizer import OllamaLLMTextSummarizer


def main():
    model_names = ["llama3.2", "gemma2", "mistral", "codellama"]
    sqlite_file_name = "summaries.db"
    rss_feed_urls = [
        "https://computer.rip/rss.xml",
        "https://www.filfre.net/feed/rss/",
        "https://blog.plover.com/index.rss",
        "https://medium.com/feed/@admiralcloudberg",
    ]
    sqlite_connection = SQLiteConnection(sqlite_file_name)

    for model_name in model_names:
        for feed_url in rss_feed_urls:
            rss_summarizer = RSSSummarizer(
                feed_url,
                OllamaLLMTextSummarizer(model_name),
                sqlite_connection,
            )
            rss_summarizer.process_rss_feed()


if __name__ == "__main__":
    main()
