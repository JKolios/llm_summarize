from sqlite_connection import SQLiteConnection
from rss_summarizer import RSSSummarizer
from ollama_llm_text_summarizer import OllamaLLMTextSummarizer
from telegram_bot import send_message

from time import sleep

SQLITE_SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent == false"

SQLITE_UPDATE_SENT_STATEMENT = (
    "UPDATE summaries SET sent = true  WHERE entry_guid == ? AND model == ?"
)


def telegram_message_from_summary(summary):
    return f"Feed: {summary[1]}\n\nTitle: {summary[4]}\n\nSummary:{summary[6]}\n\nLink: {summary[2]}"


def main():
    # model_names = ["llama3.2", "gemma2", "mistral", "codellama"]
    model_names = ["gemma2"]
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

    unsent_summaries = sqlite_connection.query(SQLITE_SELECT_UNSENT_STATEMENT, ())
    print(unsent_summaries)

    for summary in unsent_summaries:
        send_message(telegram_message_from_summary(summary))
        result = sqlite_connection.execute_and_commit(
            SQLITE_UPDATE_SENT_STATEMENT, (summary[2], summary[3])
        )
        print(result)
        sleep(5)


if __name__ == "__main__":
    main()
