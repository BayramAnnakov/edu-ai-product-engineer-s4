# pyright: reportAttributeAccessIssue=false
"""Upload a skill bundle from cohort-agent/skills/<name>/ to Anthropic.

Prints the resulting skill_id; stage it as a Fly secret so provision.py
can attach it on the next agent (re)provisioning.

Usage:

    cd cohort-agent
    source venv/bin/activate
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m scripts.upload_skill --name cohort-search
    python -m scripts.upload_skill --name dossier-creator

    fly secrets set --app edu-aipe-s4-tars \\
        COHORT_SEARCH_SKILL_ID=skill_... \\
        COHORT_DOSSIER_CREATOR_SKILL_ID=skill_...
    python provision.py  # re-attach with new skills

Adapted from onsa-robin/scripts/upload_skill.py — same SDK call shape.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anthropic import Anthropic

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--name", required=True,
        help="Skill bundle directory name under cohort-agent/skills/",
    )
    ap.add_argument(
        "--display-title", default=None,
        help="Display title (default: skill name humanized)",
    )
    args = ap.parse_args()

    skill_dir = SKILLS_ROOT / args.name
    if not skill_dir.exists():
        print(f"ERROR: {skill_dir} not found", file=sys.stderr)
        return 1
    if not (skill_dir / "SKILL.md").exists():
        print(f"ERROR: {skill_dir}/SKILL.md missing — every skill must have one",
              file=sys.stderr)
        return 1

    display_title = args.display_title or args.name.replace("-", " ").title()

    # API requires SKILL.md to live inside a top-level folder named after
    # the skill, so prefix every uploaded path with `<name>/`.
    files: list[tuple[str, bytes, str]] = []
    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        rel = f"{args.name}/{f.relative_to(skill_dir).as_posix()}"
        mime = "text/markdown" if rel.endswith(".md") else "application/octet-stream"
        files.append((rel, f.read_bytes(), mime))

    print(f"Uploading {len(files)} file(s) for skill '{display_title}':")
    for fname, content, mime in files:
        print(f"  {fname} ({len(content)} bytes, {mime})")

    client = Anthropic()
    resp = client.beta.skills.create(display_title=display_title, files=files)
    print()
    print("Created skill:")
    print(f"  id            = {resp.id}")
    print(f"  display_title = {resp.display_title!r}")
    for attr in ("latest_version", "version", "created_at"):
        if hasattr(resp, attr):
            print(f"  {attr:13} = {getattr(resp, attr)!r}")

    print()
    print("Stage as Fly secret:")
    name_upper = args.name.upper().replace('-', '_')
    # Avoid doubled `COHORT_` prefix when the skill name already starts with cohort-
    if name_upper.startswith("COHORT_"):
        env_var = f"{name_upper}_SKILL_ID"
    else:
        env_var = f"COHORT_{name_upper}_SKILL_ID"
    print(f"  fly secrets set --app edu-aipe-s4-tars {env_var}={resp.id}")
    print()
    print()
    print("Then re-provision (locally or via fly):")
    print(f"  export {env_var}={resp.id}")
    print(f"  python provision.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
