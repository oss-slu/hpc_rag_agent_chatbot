"""Load a documentation snapshot and split its pages into chunks for search.

A snapshot is a folder with one Markdown file per page. Each file starts with
``<!-- Source: <url> | Retrieved: <time> -->``. Nothing here touches the network.

Check a snapshot without writing anything:

    uv run python -m slu_hpc_rag.ingest.chunking --dry-run data/snapshots/2026-09-30
"""

import argparse
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

MAX_TOKENS = 800  # per chunk, heading path included
OVERLAP_TOKENS = 100  # text repeated from the end of the previous chunk
LIBRA_HOST = "docs.libra.slu.edu"

_HEADER = re.compile(r"^<!--\s*Source:\s*(\S+)\s*\|\s*Retrieved:\s*(.*?)\s*-->\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
_TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
_PERMALINK = re.compile(r"\[¶\]\([^)]*\)|¶")
# Site navigation, header and footer text that the scraper can leave behind.
_NAV_LINE = re.compile(
    r"^\s*(skip to content|back to top|table of contents|edit this page|legal notices"
    r"|previous|next|made with material for mkdocs.*|last modified.*"
    r"|\[(previous|next)\b[^\]]*\]\([^)]*\)|\[(skip to content|back to top)\]\([^)]*\))\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Page:
    slug: str
    url: str
    title: str
    source: str  # "libra" or "slurm"
    markdown: str


@dataclass(frozen=True)
class DocChunk:
    slug: str
    url: str
    heading: str  # e.g. "Submit a Job > GPU jobs"
    ordinal: int
    body: str  # heading path, a blank line, then the section text

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.body)


@dataclass(frozen=True)
class _Block:
    text: str
    atomic: bool  # code blocks and tables are never cut


def estimate_tokens(text: str) -> int:
    """Rough token count (about 4 characters per token)."""
    return (len(text) + 3) // 4


def source_for(url: str) -> str:
    return "libra" if urlparse(url).hostname == LIBRA_HOST else "slurm"


def load_snapshot(path: str | Path) -> list[Page]:
    """Read every page in a snapshot folder (or its ``markdown/`` subfolder)."""
    root = Path(path)
    if (root / "markdown").is_dir():
        root = root / "markdown"
    files = sorted(f for f in root.rglob("*.md") if not f.name.startswith("."))
    if not files:
        raise FileNotFoundError(f"no Markdown pages found in {root}")

    pages: dict[str, Page] = {}
    for file in files:
        text = file.read_text(encoding="utf-8")
        match = _HEADER.match(text.partition("\n")[0])
        if not match:
            raise ValueError(
                f"{file}: first line must be <!-- Source: <url> | Retrieved: <time> -->"
            )
        url = match.group(1)
        slug = _slug(file.relative_to(root))
        if slug in pages:
            raise ValueError(f"{file}: another file already has the slug {slug!r}")
        pages[slug] = Page(slug, url, _title(text) or slug, source_for(url), text)
    return list(pages.values())


def clean(markdown: str) -> str:
    """Drop the source header and leftover site navigation; code blocks are left as-is."""
    lines = markdown.splitlines()
    if lines and _HEADER.match(lines[0]):
        lines = lines[1:]
    out: list[str] = []
    fence = None
    for line in lines:
        if fence:
            out.append(line)
            if _closes(line, fence):
                fence = None
            continue
        fence = _opens(line)
        if fence:
            out.append(line)
            continue
        if _NAV_LINE.match(line):
            continue
        line = _PERMALINK.sub("", line).rstrip()
        if line or (out and out[-1]):  # collapse runs of blank lines
            out.append(line)
    return "\n".join(out).strip("\n")


def split(page: Page) -> list[DocChunk]:
    """Cut a page into chunks on #/##/### headings, capped at about MAX_TOKENS each."""
    chunks: list[DocChunk] = []
    for path, blocks in _sections(clean(page.markdown), page.title):
        heading = " > ".join(path)
        budget = MAX_TOKENS - estimate_tokens(heading + "\n\n")
        for text in _pack(blocks, budget):
            chunks.append(
                DocChunk(page.slug, page.url, heading, len(chunks), f"{heading}\n\n{text}")
            )
    return chunks


def _slug(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if len(parts) > 1 and parts[-1] == "index":
        parts.pop()
    return "-".join(parts).lower()


def _title(markdown: str) -> str | None:
    fence = None
    for line in markdown.splitlines():
        if fence:
            fence = None if _closes(line, fence) else fence
            continue
        fence = _opens(line)
        match = _HEADING.match(line)
        if not fence and match and len(match.group(1)) == 1:
            return _PERMALINK.sub("", match.group(2)).strip()
    return None


def _opens(line: str) -> str | None:
    match = _FENCE.match(line)
    return match.group(1) if match else None


def _closes(line: str, fence: str) -> bool:
    """A closing fence: same character, at least as long, indented at most 3 spaces."""
    match = _FENCE_CLOSE.match(line)
    return bool(match) and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence)


def _table_end(lines: list[str], i: int) -> int | None:
    """If a table starts at line ``i``, return the index just past its last row."""
    line = lines[i]
    if "|" not in line:
        return None
    next_line = lines[i + 1] if i + 1 < len(lines) else ""
    has_delimiter = "|" in next_line and _TABLE_DELIMITER.match(next_line)
    if not (line.lstrip().startswith("|") or has_delimiter):
        return None
    end = i + 1
    while end < len(lines) and lines[end].strip() and "|" in lines[end] and not _opens(lines[end]):
        end += 1
    return end


def _sections(text: str, title: str) -> list[tuple[list[str], list[_Block]]]:
    """Group a cleaned page into (heading path, blocks) per #/##/### heading."""
    sections: list[tuple[list[str], list[_Block]]] = [([title], [])]
    levels: dict[int, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _HEADING.match(line)
        fence = _opens(line)
        if fence:
            end = i + 1
            while end < len(lines) and not _closes(lines[end], fence):
                end += 1
            # An unclosed fence runs to the end of the page (as in Markdown); an
            # empty one is a stray marker left by the scraper, so it is dropped.
            if end < len(lines) or any(x.strip() for x in lines[i + 1 :]):
                sections[-1][1].append(_Block("\n".join(lines[i : end + 1]), atomic=True))
            i = end + 1
        elif heading and len(heading.group(1)) <= 3:
            level = len(heading.group(1))
            levels = {k: v for k, v in levels.items() if k < level}
            levels[level] = heading.group(2).strip()
            sections.append(([levels[k] for k in sorted(levels)], []))
            i += 1
        elif (table_end := _table_end(lines, i)) is not None:
            sections[-1][1].append(_Block("\n".join(lines[i:table_end]), atomic=True))
            i = table_end
        elif line.strip():
            end = i
            while end < len(lines) and _is_prose(lines, end):
                end += 1
            sections[-1][1].append(_Block("\n".join(lines[i:end]), atomic=False))
            i = end
        else:
            i += 1
    return [(path, blocks) for path, blocks in sections if blocks]


def _is_prose(lines: list[str], i: int) -> bool:
    line = lines[i]
    heading = _HEADING.match(line)
    return (
        bool(line.strip())
        and not _opens(line)
        and not (heading and len(heading.group(1)) <= 3)
        and _table_end(lines, i) is None
    )


def _pack(blocks: list[_Block], budget: int) -> list[str]:
    """Join blocks into chunks of at most ``budget`` tokens, with a short overlap."""
    # Long paragraphs are cut small enough that the overlap still fits in front.
    piece_budget = budget - OVERLAP_TOKENS - 1
    pieces: list[_Block] = []
    for block in blocks:
        if not block.atomic and estimate_tokens(block.text) > budget:
            pieces.extend(_Block(t, atomic=False) for t in _split_prose(block.text, piece_budget))
        else:
            pieces.append(block)

    chunks: list[str] = []
    current: list[_Block] = []
    for block in pieces:
        if current and _size(current + [block]) > budget:
            chunks.append(_join(current))
            current = _overlap(current)
            if current and _size(current + [block]) > budget:
                current = []
        current.append(block)
    if current:
        chunks.append(_join(current))
    return chunks


def _overlap(blocks: list[_Block]) -> list[_Block]:
    """The prose at the end of a chunk to repeat at the start of the next one."""
    tail: list[_Block] = []
    for block in reversed(blocks):
        if block.atomic:
            break
        if _size([block] + tail) > OVERLAP_TOKENS:
            if not tail:
                tail = [_Block(_last_words(block.text, OVERLAP_TOKENS * 4), atomic=False)]
            break
        tail.insert(0, block)
    return tail


def _split_prose(text: str, budget: int) -> list[str]:
    """Cut an over-long paragraph at sentence ends (or words, for huge sentences)."""
    limit = budget * 4
    words: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for word in [sentence] if len(sentence) <= limit else sentence.split():
            words.extend(word[j : j + limit] for j in range(0, len(word), limit))
    parts, current = [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > limit:
            parts.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    return parts + [current]


def _last_words(text: str, limit: int) -> str:
    """The last words of ``text``, at most ``limit`` characters."""
    kept: list[str] = []
    size = -1
    for word in reversed(text.split()):
        size += len(word) + 1
        if kept and size > limit:
            break
        kept.append(word)
    return " ".join(reversed(kept))[-limit:]


def _join(blocks: list[_Block]) -> str:
    return "\n\n".join(block.text for block in blocks)


def _size(blocks: list[_Block]) -> int:
    """Token estimate of the joined blocks, without building the string."""
    chars = sum(len(block.text) for block in blocks) + 2 * (len(blocks) - 1)
    return (max(chars, 0) + 3) // 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m slu_hpc_rag.ingest.chunking",
        description="Split a documentation snapshot into chunks.",
    )
    parser.add_argument("snapshot", type=Path, help="snapshot folder (or its markdown/ folder)")
    parser.add_argument("--dry-run", action="store_true", help="print counts; write nothing")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("only --dry-run is supported until the embed step is added")

    try:
        pages = load_snapshot(args.snapshot)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    per_page = {page.slug: split(page) for page in pages}
    sizes = [chunk.tokens for chunks in per_page.values() for chunk in chunks]
    libra = sum(page.source == "libra" for page in pages)
    print(f"pages:  {len(pages)} (libra {libra}, slurm {len(pages) - libra})")
    print(f"chunks: {len(sizes)}")
    if sizes:
        median = statistics.median(sizes)
        print(f"chunk size (est. tokens): min {min(sizes)} / median {median:g} / max {max(sizes)}")
    empty = [slug for slug, chunks in per_page.items() if not chunks]
    if empty:
        print(f"pages with zero chunks ({len(empty)}): " + ", ".join(empty))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
