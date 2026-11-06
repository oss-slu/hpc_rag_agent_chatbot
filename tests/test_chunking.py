from pathlib import Path

import pytest

from slu_hpc_rag.ingest import chunking
from slu_hpc_rag.ingest.chunking import Page, clean, estimate_tokens, load_snapshot, split

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshot"


def page(markdown: str, slug: str = "p", title: str = "Doc") -> Page:
    return Page(slug, "https://example.edu/p/", title, "slurm", markdown)


@pytest.fixture(scope="module")
def pages() -> dict[str, Page]:
    return {p.slug: p for p in load_snapshot(SNAPSHOT)}


# --- load_snapshot ---


def test_header_parsing(pages):
    assert set(pages) == {"how-to-submit-job", "reference-queues", "reference-long-script"}
    job = pages["how-to-submit-job"]
    assert job.url == "https://example.edu/how-to/submit-job/"


def test_title_comes_from_first_h1(pages):
    assert pages["how-to-submit-job"].title == "Submit a Job"
    assert pages["reference-queues"].title == "Example Queues"  # permalink mark removed


def test_title_falls_back_to_slug(tmp_path):
    (tmp_path / "no-title.md").write_text(
        "<!-- Source: https://example.edu/x/ | Retrieved: now -->\n```\n# not a title\n```\nText\n"
    )
    assert load_snapshot(tmp_path)[0].title == "no-title"


def test_source_is_libra_only_for_libra_docs(pages):
    assert {p.source for p in pages.values()} == {"slurm"}
    assert chunking.source_for("https://docs.libra.slu.edu/how-to/x/") == "libra"
    assert chunking.source_for("https://slurm.schedmd.com/sbatch.html") == "slurm"


def test_accepts_markdown_folder_directly(pages):
    assert len(load_snapshot(SNAPSHOT / "markdown")) == len(pages)


def test_missing_header_is_an_error(tmp_path):
    (tmp_path / "bad.md").write_text("# No header\n")
    with pytest.raises(ValueError, match="Source"):
        load_snapshot(tmp_path)


def test_duplicate_slug_is_an_error(tmp_path):
    header = "<!-- Source: https://example.edu/a/ | Retrieved: now -->\n# A\n"
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.md").write_text(header)
    (tmp_path / "a-b.md").write_text(header)
    with pytest.raises(ValueError, match="slug"):
        load_snapshot(tmp_path)


def test_empty_folder_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_snapshot(tmp_path)


# --- clean ---


def test_clean_drops_header_and_navigation(pages):
    text = clean(pages["how-to-submit-job"].markdown)
    assert "<!-- Source" not in text
    for nav in ("Skip to content", "Previous:", "Next:", "Back to top", "Made with Material"):
        assert nav not in text
    assert text.startswith("# Submit a Job")


def test_clean_keeps_code_blocks_untouched():
    md = "# T\n\n```\nnext\n\n\n¶ keep\n```\n"
    assert "next\n\n\n¶ keep" in clean(md)


def test_clean_drops_linked_navigation():
    md = "[Skip to content](#main)\n# T\n\nText\n\n[Back to top](#top)\n"
    assert clean(md) == "# T\n\nText"


def test_clean_collapses_blank_lines():
    assert clean("# T\n\n\n\nText\n") == "# T\n\nText"


# --- split ---


def test_table_stays_intact(pages):
    chunks = split(pages["reference-queues"])
    table = [c for c in chunks if "| Queue |" in c.body]
    assert len(table) == 1
    assert all(row in table[0].body for row in ("| alpha |", "| beta |", "| gamma |"))


def test_table_without_outer_pipes_stays_intact():
    rows = "\n".join(f"row{i} | value{i}" for i in range(500))
    chunks = split(page(f"# Doc\n\nKey | Value\n--- | ---\n{rows}\n\nAfter."))
    [table] = [c for c in chunks if "Key | Value" in c.body]
    assert "row0 | value0" in table.body and "row499 | value499" in table.body


def test_horizontal_rule_is_not_a_table():
    [chunk] = split(page("# Doc\n\nAbove\n\n---\n\nBelow | with a pipe"))
    assert chunk.body == "Doc\n\nAbove\n\n---\n\nBelow | with a pipe"


def test_indented_backticks_do_not_close_a_fence():
    code = "\n".join(f"line {i}" for i in range(700))
    md = f"# Doc\n\n```\nstart\n    ```\n## still code\n{code}\n```\n"
    [chunk] = split(page(md))
    assert chunk.heading == "Doc"
    assert "## still code" in chunk.body and "line 699" in chunk.body


def test_heading_right_after_a_table_is_not_swallowed():
    chunks = split(page("# Doc\n\nA | B\n--- | ---\nx | y\n## CPU | GPU\nDetails."))
    assert [c.heading for c in chunks] == ["Doc", "Doc > CPU | GPU"]


def test_clean_keeps_table_cells_untouched():
    md = "# Doc ¶\n\n| A |\n| --- |\n| ¶ |"
    assert clean(md) == "# Doc\n\n| A |\n| --- |\n| ¶ |"


def test_code_block_is_never_split(pages):
    for p in pages.values():
        for c in split(p):
            assert c.body.count("```") % 2 == 0, (p.slug, c.ordinal)


def test_heading_inside_code_block_is_not_a_split_point(pages):
    gpu = [c for c in split(pages["how-to-submit-job"]) if "#SBATCH --gpus=1" in c.body]
    assert len(gpu) == 1
    assert "## this line is a comment" in gpu[0].body


def test_oversized_code_block_kept_whole(pages):
    chunks = split(pages["reference-long-script"])
    [code] = [c for c in chunks if "```bash" in c.body]
    assert "#SBATCH --job-name=example-pipeline" in code.body
    assert 'log "pipeline finished"' in code.body
    assert "# Settings" in code.body  # comment lines inside code are not headings
    assert code.tokens > chunking.MAX_TOKENS  # allowed: code is never cut


def test_heading_path(pages):
    headings = [c.heading for c in split(pages["how-to-submit-job"])]
    assert headings == [
        "Submit a Job",
        "Submit a Job > Batch jobs",
        "Submit a Job > Batch jobs > GPU jobs",
        "Submit a Job > Interactive jobs",
    ]


def test_heading_path_is_prepended(pages):
    for c in split(pages["how-to-submit-job"]):
        assert c.body.startswith(c.heading + "\n\n")


def test_level_four_headings_stay_in_their_section(pages):
    gpu = [c for c in split(pages["how-to-submit-job"]) if c.heading.endswith("GPU jobs")]
    assert "#### Tips" in gpu[0].body


def test_ordinals_count_from_zero_per_page(pages):
    for p in pages.values():
        chunks = split(p)
        assert [c.ordinal for c in chunks] == list(range(len(chunks)))
        assert all(c.slug == p.slug and c.url == p.url for c in chunks)


def test_long_prose_is_capped_with_overlap():
    sentences = [f"Sentence number {i} explains one small example idea." for i in range(400)]
    md = "# Long\n\n" + "\n\n".join(" ".join(sentences[i : i + 10]) for i in range(0, 400, 10))
    chunks = split(page(md, title="Long"))
    assert len(chunks) > 1
    assert all(c.tokens <= chunking.MAX_TOKENS for c in chunks)
    for a, b in zip(chunks, chunks[1:], strict=False):
        tail = a.body.split()[-5:]
        assert " ".join(tail) in b.body  # next chunk repeats the end of this one


def test_one_huge_paragraph_is_cut():
    md = "# Big\n\n" + " ".join(f"word{i}" for i in range(2000))
    chunks = split(page(md, title="Big"))
    assert len(chunks) > 1
    assert all(c.tokens <= chunking.MAX_TOKENS for c in chunks)
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert " ".join(a.body.split()[-5:]) in b.body  # overlap survives the cut


def test_overlap_between_near_cap_paragraphs():
    chunks = split(page("# Doc\n\n" + "a " * 1450 + "\n\n" + "b " * 1450))
    assert len(chunks) > 1
    assert all(c.tokens <= chunking.MAX_TOKENS for c in chunks)
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert " ".join(a.body.split()[-5:]) in b.body


def test_very_long_heading_does_not_crash():
    chunks = split(page("# Doc\n\n## " + "h" * 2794 + "\n\n" + "word " * 1000))
    assert len(chunks) > 1


def test_one_huge_word_is_cut():
    chunks = split(page("# Doc\n\n" + "x" * 10000))
    assert len(chunks) > 1
    assert all(c.tokens <= chunking.MAX_TOKENS for c in chunks)


def test_no_overlap_after_a_code_block():
    code = "```\n" + "x = 1\n" * 1000 + "```"
    md = f"# Doc\n\nIntro text.\n\n{code}\n\nAfter the code."
    chunks = split(page(md))
    assert [c.body.startswith("Doc\n\n```") for c in chunks] == [False, True, False]
    assert chunks[-1].body == "Doc\n\nAfter the code."


def test_unclosed_fence_runs_to_end_of_page():
    md = "# Doc\n\nIntro.\n\n```\nrun_this\n\n## not a heading\n\nmore code"
    [chunk] = split(page(md))
    assert chunk.heading == "Doc"
    assert chunk.body.endswith("```\nrun_this\n\n## not a heading\n\nmore code")


def test_stray_empty_fence_is_dropped():
    [chunk] = split(page("# Doc\n\nLast paragraph.\n\n```\n"))
    assert chunk.body == "Doc\n\nLast paragraph."


def test_page_with_no_text_has_no_chunks():
    assert split(page("# Only a title\n")) == []


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


# --- CLI ---


def test_dry_run_prints_counts(capsys):
    assert chunking.main(["--dry-run", str(SNAPSHOT)]) == 0
    out = capsys.readouterr().out
    assert "pages:  3 (libra 0, slurm 3)" in out
    assert "chunks:" in out
    assert "min" in out and "median" in out and "max" in out


def test_dry_run_flags_pages_with_zero_chunks(tmp_path, capsys):
    (tmp_path / "empty.md").write_text(
        "<!-- Source: https://example.edu/e/ | Retrieved: now -->\n"
    )
    assert chunking.main(["--dry-run", str(tmp_path)]) == 1
    assert "zero chunks (1): empty" in capsys.readouterr().out


def test_cli_reports_bad_snapshot(tmp_path, capsys):
    assert chunking.main(["--dry-run", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_requires_dry_run():
    with pytest.raises(SystemExit):
        chunking.main([str(SNAPSHOT)])
