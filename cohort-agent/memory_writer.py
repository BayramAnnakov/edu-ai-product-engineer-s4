# pyright: reportAttributeAccessIssue=false
"""Direct read/write access to TARS's memory stores from outside the session.

Used by:
- post-session transcript ingestion (`python memory_writer.py write /transcripts/lesson-1-2026-05-02.md path/to/transcript.txt`)
- ad-hoc seed updates between provisioning runs
- introspection (list, read, history)
- audit / scrub (delete a leaked memory; redact a historical version)

Inside a session, the agent reads each store from a directory under
`/mnt/memory/` (the platform tells the agent the exact mount path via the
auto-injected system-prompt note — we don't hardcode it). This module talks to
the memory_stores REST surface for orchestrator-side ops only.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from anthropic import Anthropic

KNOWLEDGE_STORE_ENV = "COHORT_KNOWLEDGE_STORE_ID"
LEARNINGS_STORE_ENV = "COHORT_LEARNINGS_STORE_ID"


def _client() -> Anthropic:
    return Anthropic()


def _store_id(which: str) -> str:
    env = KNOWLEDGE_STORE_ENV if which == "knowledge" else LEARNINGS_STORE_ENV
    sid = (os.environ.get(env) or "").strip()
    if not sid:
        sys.exit(f"set {env}")
    return sid


def _path_prefix_for(path: str) -> str:
    """Narrow the list call to the directory containing `path`.

    The list endpoint matches `path_prefix` as a literal prefix, so passing
    e.g. `/digests/` returns only `/digests/...` records. For an exact-match
    lookup we still iterate, but on a much smaller page.
    """
    if "/" not in path[1:]:
        return "/"
    return path[: path.rindex("/") + 1]


def _resolve(client: Anthropic, store_id: str, path: str) -> tuple[str | None, str | None]:
    """Return (memory_id, content_sha256) for `path`, or (None, None)."""
    page = client.beta.memory_stores.memories.list(
        memory_store_id=store_id,
        path_prefix=_path_prefix_for(path), depth=10, order_by="path",
    )
    for m in (page.data if hasattr(page, "data") else page):
        if getattr(m, "path", "") == path:
            return getattr(m, "id", None), getattr(m, "content_sha256", None)
    return None, None


def write(store: str, path: str, content: str) -> None:
    client = _client()
    sid = _store_id(store)
    mid, sha = _resolve(client, sid, path)
    if mid:
        client.beta.memory_stores.memories.update(
            memory_id=mid, memory_store_id=sid, content=content,
            precondition=(
                {"type": "content_sha256", "content_sha256": sha} if sha else None
            ),
        )
        print(f"[{store}] updated {path}")
    else:
        client.beta.memory_stores.memories.create(sid, path=path, content=content)
        print(f"[{store}] created {path}")


def read(store: str, path: str) -> None:
    client = _client()
    sid = _store_id(store)
    mid, _ = _resolve(client, sid, path)
    if not mid:
        sys.exit(f"not found: {path}")
    m = client.beta.memory_stores.memories.retrieve(memory_id=mid, memory_store_id=sid)
    print(getattr(m, "content", ""))


def listing(store: str, prefix: str = "/") -> None:
    client = _client()
    sid = _store_id(store)
    page = client.beta.memory_stores.memories.list(
        memory_store_id=sid,
        path_prefix=prefix, depth=10, order_by="path",
    )
    for m in (page.data if hasattr(page, "data") else page):
        print(getattr(m, "path", ""))


def delete(store: str, path: str) -> None:
    """Permanently delete a memory by path.

    Use to scrub a leaked instructor-only file out of a student-facing store, or
    to retire stale content. The version history of the deleted memory survives
    in the store's audit trail (per docs: "versions outlive their parent").
    """
    client = _client()
    sid = _store_id(store)
    mid, _ = _resolve(client, sid, path)
    if not mid:
        sys.exit(f"not found: {path}")
    client.beta.memory_stores.memories.delete(memory_id=mid, memory_store_id=sid)
    print(f"[{store}] deleted {path}")


def history(store: str, path: str) -> None:
    """Print version history for a memory path, newest first."""
    client = _client()
    sid = _store_id(store)
    mid, _ = _resolve(client, sid, path)
    if not mid:
        sys.exit(f"not found: {path}")
    versions = client.beta.memory_stores.memory_versions.list(
        sid, memory_id=mid,
    )
    items = versions.data if hasattr(versions, "data") else versions
    for v in items:
        print(
            f"{getattr(v, 'id', '?')}  {getattr(v, 'operation', '?'):8s}  "
            f"{getattr(v, 'created_at', '?')}"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    w = sp.add_parser("write")
    w.add_argument("path", help="memory path, e.g. /transcripts/lesson-1-2026-05-02.md")
    w.add_argument("file", help="local file to upload (- for stdin)")
    w.add_argument("--store", default="knowledge", choices=["knowledge", "learnings"])

    r = sp.add_parser("read")
    r.add_argument("path")
    r.add_argument("--store", default="knowledge", choices=["knowledge", "learnings"])

    ls = sp.add_parser("list")
    ls.add_argument("--prefix", default="/")
    ls.add_argument("--store", default="knowledge", choices=["knowledge", "learnings"])

    d = sp.add_parser("delete")
    d.add_argument("path")
    d.add_argument("--store", default="knowledge", choices=["knowledge", "learnings"])

    h = sp.add_parser("history")
    h.add_argument("path")
    h.add_argument("--store", default="knowledge", choices=["knowledge", "learnings"])

    args = ap.parse_args()

    if args.cmd == "write":
        if args.file == "-":
            content = sys.stdin.read()
        else:
            content = Path(args.file).read_text(encoding="utf-8")
        write(args.store, args.path, content)
    elif args.cmd == "read":
        read(args.store, args.path)
    elif args.cmd == "list":
        listing(args.store, args.prefix)
    elif args.cmd == "delete":
        delete(args.store, args.path)
    elif args.cmd == "history":
        history(args.store, args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
