"""Check the process documents in docs/procesos: required sections, Mermaid flow, valid relative links and
that every documented endpoint exists in app/main.py. No third-party dependencies."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "procesos"
SECTIONS = ["Purpose", "Roles", "Flow", "Procedure", "Controls", "Audit evidence"]
ROUTE = re.compile(r"`(GET|POST|PUT|DELETE) (/[^`\s]*)`")


def routes() -> set[tuple[str, str]]:
    src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    return {(m[0].upper(), m[1]) for m in re.findall(r'@app\.(get|post|put|delete)\("([^"]+)"', src)}


def check(path: Path, known: set[tuple[str, str]]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errs = []
    if path.name != "README.md":
        for s in SECTIONS:
            if not re.search(rf"^## {s}\s*$", text, re.M):
                errs.append(f"{path.name}: missing section '{s}'")
        if "```mermaid" not in text:
            errs.append(f"{path.name}: no mermaid flow")
        for method, route in ROUTE.findall(text):
            if (method, route) not in known:
                errs.append(f"{path.name}: endpoint {method} {route} not in app/main.py")
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text):
        if not target.startswith(("http://", "https://")) and not (path.parent / target).exists():
            errs.append(f"{path.name}: broken link {target}")
    return errs


def main() -> int:
    known = routes()
    errs: list[str] = []
    files = sorted(DOCS.glob("*.md"))
    if len(files) < 4:
        errs.append("expected README.md plus at least 3 process documents")
    for f in files:
        errs += check(f, known)
    readme = (DOCS / "README.md").read_text(encoding="utf-8")
    for f in files:
        if f.name != "README.md" and f.name not in readme:
            errs.append(f"README.md does not list {f.name}")
    for e in errs:
        print("ERROR", e)
    print(f"{len(files)} files checked, {len(errs)} errors")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
