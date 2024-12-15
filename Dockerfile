FROM ghcr.io/astral-sh/uv:0.5.9-python3.12-alpine

WORKDIR /app
ADD pyproject.toml /app
ADD uv.lock /app
RUN  uv sync --frozen --no-install-project --verbose

ADD *.py /app

CMD uv run python telegram_bot.py