FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm AS base
WORKDIR /app
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN apt-get update && apt-get install --no-install-recommends -y \
    poppler-utils tesseract-ocr tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*
RUN uv sync --no-dev --no-install-project
COPY . .
ENV PATH="/opt/venv/bin:$PATH"
# Bake the local procedure model into the image so runtime/import needs no Hugging Face download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
