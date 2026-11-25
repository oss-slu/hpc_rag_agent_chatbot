import json

import pytest
from pydantic import ValidationError

from slu_hpc_rag import retrieval
from slu_hpc_rag.contracts import Chunk, Finding
from slu_hpc_rag.tools.slurm_check import check_script

CHUNK = Chunk(
    url="https://example.edu/how-to/batch-jobs/",
    title="Batch jobs",
    heading="Batch jobs > Submitting",
    source="libra",
    body="Made-up text.",
    score=0.5,
)
FINDING = Finding(
    severity="error",
    rule="gpu-on-cpu-partition",
    line=3,
    message="Made-up message.",
    doc_url="https://example.edu/partitions/",
)


@pytest.mark.parametrize("value", [CHUNK, FINDING])
def test_round_trips_through_json(value):
    restored = type(value).model_validate(json.loads(value.model_dump_json()))
    assert restored == value


def test_search_artifact_dicts_carry_the_citation_fields():
    # The search_docs artifact is a list of chunk.model_dump(); the API reads title and url.
    as_dict = CHUNK.model_dump()
    assert as_dict["title"] == CHUNK.title and as_dict["url"] == CHUNK.url
    assert CHUNK.citation() == {
        "title": "Batch jobs",
        "url": "https://example.edu/how-to/batch-jobs/",
    }


def test_contract_values_are_checked():
    with pytest.raises(ValidationError):
        Chunk(**{**CHUNK.model_dump(), "source": "wikipedia"})
    with pytest.raises(ValidationError):
        Finding(**{**FINDING.model_dump(), "severity": "fatal"})
    with pytest.raises(ValidationError):
        Finding(**{**FINDING.model_dump(), "line": 0})  # lines are 1-based
    assert Finding(**{**FINDING.model_dump(), "line": None}).line is None  # whole script


def test_finding_line_can_be_left_out():
    # A problem with the whole script (e.g. no #SBATCH --time) has no line to point at.
    finding = Finding(severity="warning", rule="no-time-limit", message="Made-up message.")
    assert finding.line is None


def test_contracts_are_immutable():
    with pytest.raises(ValidationError):
        CHUNK.score = 1.0


def test_search_stub_returns_complete_chunks():
    results = retrieval.search("anything")
    assert results and all(isinstance(c, Chunk) for c in results)
    for chunk in results:
        assert all(value not in ("", None) for value in chunk.model_dump().values())
        assert chunk.url.startswith("https://example.edu/")  # never real SLU data
    assert [c.score for c in results] == sorted((c.score for c in results), reverse=True)
    assert len(retrieval.search("anything", k=1)) == 1


def test_slurm_check_stub_finds_nothing():
    assert check_script("#!/bin/bash\n#SBATCH --time=1:00:00\n") == []
