#!/usr/bin/env python3
"""Tests for check_secrets.py against the real gitleaks binary. Usage: python3 scripts/test_check_secrets.py
Runs in validate-store.yml (which installs gitleaks), not in release-store.yml."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_secrets as c  # noqa: E402

fails = 0


def ok(cond, msg):
    global fails
    print(("ok   " if cond else "FEHL ") + msg)
    if not cond:
        fails += 1


# Invented values (no real secret anywhere in this file).
COMPOSE = """services:
  db:
    environment:
      - POSTGRES_PASSWORD=Hj7kL2mN9pQ4rS6tV8wX1yZ3
"""


def store(compose, known):
    d = Path(tempfile.mkdtemp())
    (d / "Apps" / "Demo").mkdir(parents=True)
    (d / "Apps" / "Demo" / "docker-compose.yml").write_text(compose)
    (d / "scripts").mkdir()
    (d / "scripts" / "known_secrets.json").write_text(json.dumps({"known": known}))
    return d


def run(d):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = c.main([str(d)])
    return rc, buf.getvalue()


d = store(COMPOSE, [])
found = c.findings(d)
ok(len(found) == 1 and found[0]["key"] == "POSTGRES_PASSWORD"
   and found[0]["file"] == "Apps/Demo/docker-compose.yml", "gitleaks finds the fixed password, key and path read")
rc, out = run(d)
ok(rc == 1 and "NEW  Apps/Demo/docker-compose.yml:4" in out, "unknown finding -> rc 1, file:line named")
ok("Hj7kL2mN9pQ4rS6tV8wX1yZ3" not in out, "value is never printed")

known = [{"file": f["file"], "key": f["key"], "sha256": f["sha256"]} for f in found]
rc, out = run(store(COMPOSE, known))
ok(rc == 0, "known finding -> rc 0")

rc, out = run(store("# moved down\n\n" + COMPOSE, known))
ok(rc == 0, "same finding on another line stays known")

rc, out = run(store(COMPOSE.replace("Hj7kL2mN9pQ4rS6tV8wX1yZ3", "Qw3eR5tY7uI9oP1aS2dF4gH6"), known))
ok(rc == 1 and "note: known entry no longer found" in out, "changed value under a known key -> new + note")

rc, out = run(store(COMPOSE + "      - EXTRA_API_TOKEN=Zq8vR3mK9pL2xW7nT4bY6cF1\n", known))
ok(rc == 1 and "EXTRA_API_TOKEN" in out, "new key next to a known one -> rc 1")

other = [{"file": "Apps/Other/docker-compose.yml", "key": k["key"], "sha256": k["sha256"]} for k in known]
rc, out = run(store(COMPOSE, other))
ok(rc == 1, "same key and value in another app is not covered")

print(f"\n{fails} FEHLER" if fails else "\nalles ok")
sys.exit(1 if fails else 0)
