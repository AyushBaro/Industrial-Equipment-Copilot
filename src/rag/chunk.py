"""Turn the maintenance corpus into retrievable chunks.

Each markdown doc is split by its top-level `##` sections. Front-matter is parsed into
chunk *metadata* (never embedded as text). Chunk ids are deterministic so the index is
reproducible: "{doc_id}#{section-slug}".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from src import config
from src.docs_gen.validate_corpus import load_corpus


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    doc_type: str
    subsystem: str
    title: str          # doc title
    section: str        # section heading (or "overview")
    text: str           # section body, prefixed with doc+section context
    cites_sensors: tuple

    def to_metadata(self) -> dict:
        d = asdict(self)
        d["cites_sensors"] = ",".join(str(s) for s in self.cites_sensors)
        return d


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split markdown body on '## ' headings → [(section_title, section_text), ...]."""
    parts = re.split(r"(?m)^##\s+", body)
    sections: list[tuple[str, str]] = []
    # text before the first '## ' (e.g. the H1 title line) becomes 'overview'
    head = parts[0].strip()
    if head:
        # drop a leading '# Title' line if present
        head = re.sub(r"(?m)\A#\s+.*\n?", "", head).strip()
        if head:
            sections.append(("overview", head))
    for part in parts[1:]:
        lines = part.splitlines()
        title = lines[0].strip() if lines else "section"
        text = "\n".join(lines[1:]).strip()
        if text:
            sections.append((title, text))
    return sections


def build_chunks(corpus_dir=None) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in load_corpus(corpus_dir):
        m = doc.meta
        doc_id = m["id"]
        title = m.get("title", doc_id)
        sections = _split_sections(doc.body) or [("overview", doc.body.strip())]
        for sec_title, sec_text in sections:
            cid = f"{doc_id}#{_slug(sec_title)}"
            # Prefix gives the embedder + the LLM lightweight context about the source.
            text = f"[{title} — {sec_title}]\n{sec_text}"
            chunks.append(
                Chunk(
                    id=cid,
                    doc_id=doc_id,
                    doc_type=m["type"],
                    subsystem=str(m.get("subsystem", "")),
                    title=title,
                    section=sec_title,
                    text=text,
                    cites_sensors=tuple(m.get("cites_sensors", []) or []),
                )
            )
    return chunks


if __name__ == "__main__":
    cs = build_chunks()
    print(f"{len(cs)} chunks from corpus.")
    for c in cs[:5]:
        print(f"  {c.id}  ({c.doc_type}/{c.subsystem})")
