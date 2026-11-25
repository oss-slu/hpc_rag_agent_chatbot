"""Shapes shared by search, the agent, the API and the UI.

These are the agreed interfaces between parts of the system that different
people build. Changing a field breaks someone else's code, so a change here
needs a review from everyone who uses it.

- ``Chunk`` is one search result. ``retrieval.search`` returns them, and the
  ``search_docs`` tool returns them as its artifact, each one as
  ``chunk.model_dump()`` (plain dicts, so agent state stays JSON-safe). The API
  reads ``title`` and ``url`` from those dicts to list an answer's sources.
- ``Finding`` is one problem the SLURM script checker found.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocSource = Literal["libra", "slurm"]
Severity = Literal["error", "warning", "info"]


class Chunk(BaseModel):
    """One search result: a section of a documentation page."""

    model_config = ConfigDict(frozen=True)

    url: str  # page the text comes from; cited in answers
    title: str  # page title
    heading: str  # section path, e.g. "Submit a Job > GPU jobs"
    source: DocSource  # "libra" for the Libra docs, "slurm" for SLURM's own docs
    body: str  # the section text the model reads
    score: float  # relevance; higher is better (only comparable within one search)

    def citation(self) -> dict[str, str]:
        """The ``{"title", "url"}`` pair listed under an answer."""
        return {"title": self.title, "url": self.url}


class Finding(BaseModel):
    """One problem in a SLURM job script."""

    model_config = ConfigDict(frozen=True)

    severity: Severity
    rule: str  # stable id, e.g. "gpu-on-cpu-partition"
    line: int | None = Field(default=None, ge=1)  # 1-based line; None = whole script
    message: str  # one sentence for the user
    doc_url: str | None = None  # documentation page that explains the rule
