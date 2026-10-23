# Build stage: resolve dependencies from the lockfile with uv.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# Runtime stage: only the virtualenv, run as an unprivileged user.
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app /srv/.venv /srv/.venv
ENV PATH=/srv/.venv/bin:$PATH PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "slu_hpc_rag.main:app", "--host", "0.0.0.0", "--port", "8000"]
