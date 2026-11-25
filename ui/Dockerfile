# Chat UI image. Build from the repo root: docker build -f ui/Dockerfile .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv
COPY pyproject.toml uv.lock ./
# Only the ui group: Streamlit, httpx and pydantic, not the backend's dependencies.
# --no-build: install only prebuilt wheels, so no package's setup code runs.
RUN uv sync --locked --only-group ui --no-install-project --no-build

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /srv
COPY --from=build --chown=app /srv/.venv /srv/.venv
# The UI needs only the event format from the backend package.
COPY src/slu_hpc_rag/__init__.py src/slu_hpc_rag/contracts.py src/slu_hpc_rag/stream.py ./src/slu_hpc_rag/
COPY ui/*.py ui/style.css ./ui/
COPY ui/assets/ ./ui/assets/
COPY .streamlit/config.toml ./.streamlit/
ENV PATH=/srv/.venv/bin:$PATH PYTHONPATH=/srv/src:/srv PYTHONUNBUFFERED=1 \
    API_URL=http://app:8000 STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"
CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
