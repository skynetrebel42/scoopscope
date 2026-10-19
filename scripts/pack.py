"""Bundle everything the Gemini planner needs into ONE file: ~/Downloads/scoopscope_pack.md

Run from the repo root:  python scripts/pack.py
On a milestone branch it includes `git diff master...HEAD` for review; on master that section is empty.
"""
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / "Downloads" / "scoopscope_pack.md"
DOCS = [".handoff-planner.md", "AGENTS.md", "PROJECT_HANDOFF.md", "KNOWN_ISSUES.md"]
MAX_DIFF = 150_000  # ponytail: hard cut keeps Gemini from choking; split the milestone if you hit it


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def main():
    diff = git("diff", "master...HEAD")
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + "\n\n[DIFF TRUNCATED: milestone too big, ask the Builder to split it]"
    parts = [
        f"# ScoopScope planner pack ({datetime.now():%Y-%m-%d %H:%M})",
        f"## Git\nBranch: {git('branch', '--show-current')}\n\n```\n{git('log', '--oneline', '-5')}\n```\n"
        f"Uncommitted:\n```\n{git('status', '--short') or '(clean)'}\n```",
        f"## Changes under review (git diff master...HEAD)\n```\n{git('diff', '--stat', 'master...HEAD') or '(none)'}\n```\n"
        f"```diff\n{diff or '(no diff: on master or nothing built yet)'}\n```",
    ]
    for name in DOCS + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docs" / "specs").glob("*.md")):
        path = ROOT / name
        if path.exists():
            parts.append(f"## FILE: {name}\n\n{path.read_text(encoding='utf-8')}")
    OUT.write_text("\n\n---\n\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
