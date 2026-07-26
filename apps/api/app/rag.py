"""RAG v1: code-aware chunking + SQLite FTS5 (BM25-ish) retrieval."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import CodeChunk, Repository

_CODE_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
}


@dataclass
class RetrievedChunk:
    path: str
    content: str
    symbol: str
    score: float
    start_line: int
    end_line: int


def _ensure_fts(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS code_chunks_fts
            USING fts5(chunk_id UNINDEXED, path, symbol, content, tokenize='porter')
            """
        )
    )
    db.commit()


def _path_allowed(path: str, filters: list[str]) -> bool:
    if not filters:
        return True
    for item in filters:
        prefix = item.rstrip("/") + "/"
        if path == item or path.startswith(prefix) or path.startswith(item):
            return True
    return False


def chunk_file(path: str, text_content: str, language: str) -> list[tuple[str, int, int, str]]:
    """Split a file into symbol-ish chunks (functions/classes/headings) or windows."""
    lines = text_content.splitlines()
    if not lines:
        return []
    pattern = {
        "python": re.compile(r"^(def |class |async def )"),
        "typescript": re.compile(r"^(export )?(async )?(function |class |const \w+ =)"),
        "javascript": re.compile(r"^(export )?(async )?(function |class |const \w+ =)"),
        "go": re.compile(r"^func "),
        "markdown": re.compile(r"^#{1,3} "),
    }.get(language)

    cuts = [0]
    symbols = {0: Path(path).name}
    if pattern:
        for i, line in enumerate(lines):
            if pattern.match(line.strip() if language == "markdown" else line):
                cuts.append(i)
                symbols[i] = line.strip()[:120]
    cuts.append(len(lines))
    cuts = sorted(set(cuts))

    chunks: list[tuple[str, int, int, str]] = []
    for idx in range(len(cuts) - 1):
        start = cuts[idx]
        end = cuts[idx + 1]
        # Keep chunks reasonably sized.
        while end - start > 80:
            piece_end = start + 80
            body = "\n".join(lines[start:piece_end])
            chunks.append((symbols.get(start, Path(path).name), start + 1, piece_end, body))
            start = piece_end
        body = "\n".join(lines[start:end])
        if body.strip():
            chunks.append((symbols.get(cuts[idx], Path(path).name), start + 1, end, body))
    return chunks


def index_worktree(
    db: Session,
    repo: Repository,
    worktree: Path,
    commit_sha: str = "",
    path_filters: list[str] | None = None,
) -> int:
    """Reindex a repository from a worktree into CodeChunk + FTS."""
    _ensure_fts(db)
    filters = path_filters if path_filters is not None else (repo.path_filters or [])

    # Clear previous index for this repo.
    old_ids = [c.id for c in db.query(CodeChunk).filter(CodeChunk.repository_id == repo.id).all()]
    db.query(CodeChunk).filter(CodeChunk.repository_id == repo.id).delete()
    if old_ids:
        for cid in old_ids:
            db.execute(text("DELETE FROM code_chunks_fts WHERE chunk_id = :id"), {"id": cid})
    db.commit()

    count = 0
    for path in worktree.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(worktree)).replace("\\", "/")
        if rel.startswith(".git/") or "/node_modules/" in f"/{rel}/" or "/.venv/" in f"/{rel}/":
            continue
        if not _path_allowed(rel, filters):
            continue
        language = _CODE_EXT.get(path.suffix.lower())
        if not language:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if len(content) > 200_000:
            continue
        for symbol, start, end, body in chunk_file(rel, content, language):
            cid = str(uuid.uuid4())
            db.add(
                CodeChunk(
                    id=cid,
                    repository_id=repo.id,
                    path=rel,
                    symbol=symbol,
                    language=language,
                    start_line=start,
                    end_line=end,
                    content=body,
                    commit_sha=commit_sha,
                )
            )
            db.execute(
                text(
                    "INSERT INTO code_chunks_fts(chunk_id, path, symbol, content) "
                    "VALUES (:id, :path, :symbol, :content)"
                ),
                {"id": cid, "path": rel, "symbol": symbol, "content": body},
            )
            count += 1
    db.commit()
    return count


def retrieve(
    db: Session,
    repository_id: str,
    query: str,
    limit: int = 8,
    path_filters: list[str] | None = None,
) -> list[RetrievedChunk]:
    """Hybrid-ish retrieval: FTS5 match + simple path keyword boost."""
    _ensure_fts(db)
    q = " ".join(re.findall(r"[A-Za-z0-9_]+", query))
    if not q:
        return []
    # FTS5 query: OR the terms for recall.
    fts_query = " OR ".join(q.split())
    rows = db.execute(
        text(
            """
            SELECT c.path, c.content, c.symbol, c.start_line, c.end_line,
                   bm25(code_chunks_fts) AS score
            FROM code_chunks_fts
            JOIN code_chunks c ON c.id = code_chunks_fts.chunk_id
            WHERE code_chunks_fts MATCH :q AND c.repository_id = :repo
            ORDER BY score
            LIMIT :limit
            """
        ),
        {"q": fts_query, "repo": repository_id, "limit": limit * 3},
    ).fetchall()

    results: list[RetrievedChunk] = []
    terms = [t.lower() for t in q.split()]
    for path, content, symbol, start, end, score in rows:
        if path_filters and not _path_allowed(path, path_filters):
            continue
        boost = sum(1 for t in terms if t in path.lower() or t in (symbol or "").lower())
        results.append(
            RetrievedChunk(
                path=path,
                content=content,
                symbol=symbol or "",
                score=float(score) - boost,
                start_line=start,
                end_line=end,
            )
        )
    results.sort(key=lambda r: r.score)
    return results[:limit]
