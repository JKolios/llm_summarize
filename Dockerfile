FROM ghcr.io/astral-sh/uv:0.6-python3.12-bookworm

WORKDIR /app
ADD pyproject.toml /app
ADD uv.lock /app
RUN  uv sync --frozen --no-install-project --verbose

ADD llm_summarize /app

CMD uv run python llm_summarize.py