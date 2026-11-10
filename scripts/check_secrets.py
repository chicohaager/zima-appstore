#!/usr/bin/env python3
"""Fixed secrets in the store: gitleaks (default rules) over Apps/, compared with the list of
KNOWN findings in scripts/known_secrets.json. Fails on every finding that is not on the list.

A known finding is identified by (file, key, sha256 of the value) -- not by line number, so
editing a compose does not turn the check red, but a new key, a new app, or a changed value
does. Values are never printed; the list holds only their hashes (the values themselves are
in the public composes anyway).

Why a list and not a .gitleaks.toml allowlist: an [[allowlists]] entry with `paths` frees the
WHOLE file in gitleaks 8.30.1 -- the key regex next to it had no effect (measured 2026-11-10:
an added EXTRA_API_TOKEN and MediaCMS SECRET_KEY both went unreported).

Usage:
  check_secrets.py <repo-root>                 check (exit 1 on unknown findings)
  check_secrets.py <repo-root> --list-current  print current findings as JSON (for the list)
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

KEY = re.compile(r"^\s*-?\s*\"?([A-Za-z0-9_.-]+)\"?\s*[:=]")


def findings(root):
    with tempfile.TemporaryDirectory() as d:
        rep = Path(d) / "r.json"
        r = subprocess.run(
            ["gitleaks", "dir", str(Path(root) / "Apps"), "--no-banner", "--exit-code", "0",
             "--report-format", "json", "--report-path", str(rep)],
            capture_output=True, text=True, check=False)
        if r.returncode != 0 or not rep.exists():
            raise SystemExit(f"gitleaks failed (rc={r.returncode}): {r.stderr.strip()[-500:]}")
        raw = json.loads(rep.read_text() or "[]")
    out = []
    base = str(Path(root).resolve()) + "/"
    for f in raw:
        m = KEY.match(f["Match"])
        out.append({
            "file": str(Path(f["File"]).resolve()).replace(base, ""),
            "line": f["StartLine"],
            "rule": f["RuleID"],
            "key": m.group(1) if m else "?",
            "sha256": hashlib.sha256(f["Secret"].encode()).hexdigest(),
        })
    return out


def unknown(found, known):
    k = {(e["file"], e["key"], e["sha256"]) for e in known}
    return [f for f in found if (f["file"], f["key"], f["sha256"]) not in k]


def main(a):
    if not a:
        print(__doc__)
        return 2
    root = Path(a[0])
    found = findings(root)
    if "--list-current" in a:
        keep = sorted({(f["file"], f["key"], f["sha256"]) for f in found})
        print(json.dumps([{"file": x, "key": y, "sha256": z} for x, y, z in keep], indent=2))
        return 0
    known = json.loads((root / "scripts" / "known_secrets.json").read_text())["known"]
    new = unknown(found, known)
    gone = [e for e in known
            if (e["file"], e["key"], e["sha256"]) not in {(f["file"], f["key"], f["sha256"]) for f in found}]
    print(f"gitleaks: {len(found)} findings, {len(found) - len(new)} known, {len(new)} new")
    for f in new:
        print(f"NEW  {f['file']}:{f['line']}  {f['rule']}  key {f['key']}  (value not shown)")
    for e in gone:
        print(f"note: known entry no longer found, remove it from the list: {e['file']} {e['key']}")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
