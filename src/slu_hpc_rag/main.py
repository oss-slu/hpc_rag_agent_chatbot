"""ASGI entry point: `uvicorn slu_hpc_rag.main:app`."""

from slu_hpc_rag.api import create_app

app = create_app()
