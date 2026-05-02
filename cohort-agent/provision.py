# pyright: reportAttributeAccessIssue=false
"""One-shot provisioner for TARS — the cohort 4 retrieval agent.

Run locally with ANTHROPIC_API_KEY set:

    python provision.py

Then stage the printed IDs as Fly secrets:

    fly secrets set --app edu-aipe-s4-tars \\
        COHORT_AGENT_ID=agnt_... \\
        COHORT_ENVIRONMENT_ID=env_... \\
        COHORT_KNOWLEDGE_STORE_ID=memstore_... \\
        COHORT_LEARNINGS_STORE_ID=memstore_...

Subsequent runs:
- Update the agent in-place (same ID, new version) when COHORT_AGENT_ID is set.
- Sync `memory_seeds/` into the knowledge store (creates new files, updates
  changed ones; leaves /learnings/ alone).

Adapted from onsa-robin/agent_managed/provision.py.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from anthropic import Anthropic

AGENT_NAME = "edu-aipe-s4-tars"
ENV_NAME = "edu-aipe-s4-env"
KNOWLEDGE_STORE_NAME = "cohort-knowledge"
LEARNINGS_STORE_NAME = "cohort-learnings"
MODEL = "claude-opus-4-7"

ROOT = Path(__file__).resolve().parent
CONSTITUTION_PATH = ROOT / "memory_seeds" / "00-constitution.md"
SEEDS_DIR = ROOT / "memory_seeds"


def load_system_prompt() -> str:
    if not CONSTITUTION_PATH.exists():
        sys.exit(f"missing Constitution at {CONSTITUTION_PATH}")
    return CONSTITUTION_PATH.read_text(encoding="utf-8").strip()


def compose_agent_body() -> dict:
    return {
        "name": AGENT_NAME,
        "model": MODEL,
        "system": load_system_prompt(),
        "tools": [
            {"type": "agent_toolset_20260401"},
        ],
    }


def latest_version(client: Anthropic, agent_id: str) -> int:
    res = client.beta.agents.versions.list(agent_id=agent_id, limit=1)
    versions = list(res)
    if not versions:
        raise RuntimeError(f"no versions found for agent {agent_id}")
    versions.sort(key=lambda v: getattr(v, "version", 0), reverse=True)
    return versions[0].version


def provision_agent(client: Anthropic) -> str:
    body = compose_agent_body()
    pinned = (os.environ.get("COHORT_AGENT_ID") or "").strip()

    if pinned:
        try:
            current = latest_version(client, pinned)
            update_body = {k: v for k, v in body.items() if k != "name"}
            updated = client.beta.agents.update(pinned, version=current, **update_body)
            new_v = getattr(updated, "version", None)
            print(f"[agent] updated {pinned} (v{current} -> v{new_v})")
            return pinned
        except Exception as exc:
            print(f"[agent] WARN pinned update failed ({exc!r}) - falling through", file=sys.stderr)

    existing = client.beta.agents.list(limit=100)
    matches = [a for a in existing if getattr(a, "name", None) == AGENT_NAME]
    if matches:
        agent_id = matches[0].id
        print(f"[agent] found existing {AGENT_NAME!r}: {agent_id} - pin via COHORT_AGENT_ID")
        return agent_id

    created = client.beta.agents.create(**body)
    print(f"[agent] created: id={created.id}, version={created.version}")
    return created.id


def provision_environment(client: Anthropic) -> str:
    pinned = (os.environ.get("COHORT_ENVIRONMENT_ID") or "").strip()
    if pinned:
        print(f"[env] using pinned {pinned}")
        return pinned

    existing = client.beta.environments.list(limit=100)
    matches = [e for e in existing if getattr(e, "name", None) == ENV_NAME]
    if matches:
        env_id = matches[0].id
        print(f"[env] found existing {ENV_NAME!r}: {env_id}")
        return env_id

    created = client.beta.environments.create(
        name=ENV_NAME,
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    print(f"[env] created: id={created.id}")
    return created.id


def find_or_create_store(
    client: Anthropic, name: str, description: str, pinned_env: str,
) -> str:
    pinned = (os.environ.get(pinned_env) or "").strip()
    if pinned:
        print(f"[memory] using pinned {name}: {pinned}")
        return pinned

    for s in client.beta.memory_stores.list(limit=100):
        if getattr(s, "name", None) == name:
            print(f"[memory] found existing {name!r}: {s.id} - pin via {pinned_env}")
            return s.id

    created = client.beta.memory_stores.create(name=name, description=description)
    print(f"[memory] created {name!r}: {created.id}")
    return created.id


def collect_knowledge_seeds() -> dict[str, str]:
    """Walk memory_seeds/ except 00-constitution.md (it's the system prompt)."""
    out: dict[str, str] = {}
    if not SEEDS_DIR.exists():
        return out
    for f in SEEDS_DIR.rglob("*.md"):
        if f.name == "00-constitution.md":
            continue
        rel = f.relative_to(SEEDS_DIR).as_posix()
        out[f"/{rel}"] = f.read_text(encoding="utf-8")
    return out


def sync_to_store(
    client: Anthropic, store_id: str, label: str, desired: dict[str, str],
) -> None:
    page = client.beta.memory_stores.memories.list(
        memory_store_id=store_id, depth=10, order_by="path",
    )
    existing: dict[str, tuple[str, str]] = {}
    for m in (page.data if hasattr(page, "data") else page):
        existing[getattr(m, "path", "")] = (
            getattr(m, "id", ""), getattr(m, "content_sha256", ""),
        )

    created = updated = skipped = 0
    for path, content in sorted(desired.items()):
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if path in existing:
            mid, esha = existing[path]
            if esha == sha:
                skipped += 1
                continue
            client.beta.memory_stores.memories.update(
                memory_id=mid, memory_store_id=store_id, content=content,
            )
            print(f"[{label}] updated {path}")
            updated += 1
        else:
            client.beta.memory_stores.memories.create(
                store_id, path=path, content=content,
            )
            print(f"[{label}] created {path}")
            created += 1
    print(f"[{label}] sync: {created} created, {updated} updated, {skipped} unchanged")


def seed_learnings_skeleton(client: Anthropic, store_id: str) -> None:
    skeleton = {
        "/learnings/staged/.keep": (
            "TARS stages new learnings here. One insight per file. Reviewed "
            "and promoted by Bayram periodically.\n"
        ),
    }
    page = client.beta.memory_stores.memories.list(
        memory_store_id=store_id, depth=10, order_by="path",
    )
    existing_paths = {getattr(m, "path", "") for m in (page.data if hasattr(page, "data") else page)}
    for path, content in skeleton.items():
        if path in existing_paths:
            continue
        client.beta.memory_stores.memories.create(store_id, path=path, content=content)
        print(f"[learnings] seeded skeleton: {path}")


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: set ANTHROPIC_API_KEY before running provision", file=sys.stderr)
        return 1

    client = Anthropic()
    agent_id = provision_agent(client)
    env_id = provision_environment(client)
    knowledge_id = find_or_create_store(
        client, KNOWLEDGE_STORE_NAME,
        "Curated cohort 4 knowledge: roster, lesson designs, dossiers, transcripts. "
        "Read-only for the agent except /learnings/staged/.",
        "COHORT_KNOWLEDGE_STORE_ID",
    )
    learnings_id = find_or_create_store(
        client, LEARNINGS_STORE_NAME,
        "TARS's mutable scratchpad. Agent writes to /learnings/staged/ only; "
        "Bayram promotes to /learnings/promoted/ periodically.",
        "COHORT_LEARNINGS_STORE_ID",
    )

    sync_to_store(client, knowledge_id, "knowledge", collect_knowledge_seeds())
    seed_learnings_skeleton(client, learnings_id)

    print()
    print("=" * 60)
    print("Set these as Fly secrets:")
    print()
    print("  fly secrets set --app edu-aipe-s4-tars \\")
    print(f"      COHORT_AGENT_ID={agent_id} \\")
    print(f"      COHORT_ENVIRONMENT_ID={env_id} \\")
    print(f"      COHORT_KNOWLEDGE_STORE_ID={knowledge_id} \\")
    print(f"      COHORT_LEARNINGS_STORE_ID={learnings_id}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
