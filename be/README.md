# ICIVI Backend Development Server

## Requirements

- Docker Engine with Docker Compose
- `uv` and Python 3.12 or newer for tests and migrations
- An OpenAI-compatible chat provider and an embedding provider when RAG is enabled

## Configure Local Secrets

From `be/`, create local runtime files. They are ignored by Git and must not be
copied into source control, logs, image layers, or deployment artifacts.

```sh
cp .env.example .env
cp .db.env.example .db.env
```

Set `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` in `.db.env`.
Set `DATABASE_URL` in `.env` with the same values and the Docker service host:

```dotenv
DATABASE_URL=postgresql+asyncpg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@postgres:5432/<POSTGRES_DB>
```

Also configure `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and the independent
embedding settings when testing RAG. `DATABASE_URL` is required at runtime;
the backend, migration commands, and knowledge CLI fail clearly when it is not
configured.

## Start The Development Stack

Start the API, PostgreSQL, and Redis from `be/`:

```sh
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

The API is bound to `127.0.0.1:8000`. PostgreSQL is published as
`localhost:15432` for host administration; a host tool uses
`postgresql+asyncpg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:15432/<POSTGRES_DB>`.
The backend container must use `postgres:5432`, never `localhost`.

Inspect the services when a check fails:

```sh
docker compose logs --tail=100 backend
docker compose logs --tail=100 postgres
```

After changing `.env` or `.db.env`, recreate the affected services:

```sh
docker compose up -d --force-recreate backend postgres
```

## Migrations And Knowledge Packages

Run migrations inside the configured backend container:

```sh
docker compose exec backend alembic upgrade head
```

Run registry/package validation and ingestion only after source review:

```sh
docker compose exec backend python -m app.knowledge_cli --help
```

## Host-Run Backend

For a backend process running directly on the server, set `DATABASE_URL` in
the ignored `.env` to the actual local PostgreSQL listener. With the supplied
Compose mapping that is `localhost:15432`, not `localhost:5432`.

```sh
uv sync --group dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Verify

```sh
uv run pytest -q
uv tool run pymarkdownlnt scan README.md
```
