FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm AS base
WORKDIR /app
COPY pyproject.toml ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --no-dev --no-install-project
COPY . .
ENV PATH="/opt/venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
