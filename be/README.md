# ICIVI Backend

## Requirements

- Python 3.12 or newer
- `uv`
- Redis for local execution
- Docker Compose for the full local stack

## Configure Environment

Copy the example file before starting the backend:

```sh
cp .env.example .env
```

Set `LLM_API_KEY` and `LLM_MODEL` to enable an OpenAI-compatible provider.
Without those values, the backend returns a safe mock response. For production
behind `https://icivi.online`, set `CORS_ORIGIN=https://icivi.online` and
`SESSION_COOKIE_SECURE=true`.

## Run Locally

Install dependencies and start the API from this directory:

```sh
uv sync --group dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Run With Docker Compose

From this directory, copy the environment files and run:

```sh
cp .env.example .env
cp .db.env.example .db.env
docker compose up --build
```

Docker binds the API only to `127.0.0.1:8000`. A host Nginx instance proxies
public traffic to that port.

## Test

Run the backend test suite from this directory:

```sh
uv run pytest
```
