# pyright: reportAttributeAccessIssue=false
"""Direct read/write access to TARS's memory stores from outside the session.

Used by:
- post-session transcript ingestion (`python memory_writer.py write /transcripts/lesson-1-2026-05-02.md path/to/transcript.txt`)
- ad-hoc seed updates between provisioning runs
- introspection (list, read)

Inside a session, TARS reads from `/mnt/memory/cohort-knowledge/` directly.
This module talks to the memory_stores REST surface for orchestrator-side ops.
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


def _resolve_id(client: Anthropic, store_id: str, path: str) -> str | None:
    page = client.beta.memory_stores.memories.list(
        memory_store_id=store_id, depth=10, order_by="path",
    )
    for m in (page.data if hasattr(page, "data") else page):
        if getattr(m, "path", "") == path:
            return getattr(m, "id", None)
    return None


def write(store: str, path: str, content: str) -> None:
    client = _client()
    sid = _store_id(store)
    mid = _resolve_id(client, sid, path)
    if mid:
        client.beta.memory_stores.memories.update(
            memory_id=mid, memory_store_id=sid, content=content,
        )
        print(f"[{store}] updated {path}")
    else:
        client.beta.memory_stores.memories.create(sid, path=path, content=content)
        print(f"[{store}] created {path}")


def read(store: str, path: str) -> None:
    client = _client()
    sid = _store_id(store)
    mid = _resolve_id(client, sid, path)
    if not mid:
        sys.exit(f"not found: {path}")
    m = client.beta.memory_stores.memories.retrieve(memory_id=mid, memory_store_id=sid)
    print(getattr(m, "content", ""))


def listing(store: str, prefix: str = "/") -> None:
    client = _client()
    sid = _store_id(store)
    page = client.beta.memory_stores.memories.list(
        memory_store_id=sid, depth=10, order_by="path",
    )
    for m in (page.data if hasattr(page, "data") else page):
        p = getattr(m, "path", "")
        if p.startswith(prefix):
            print(p)


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
