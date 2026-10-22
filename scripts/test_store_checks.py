#!/usr/bin/env python3
"""Tests fuer check_no_downgrade.py und add_locale_fallbacks.py. Aufruf: python3 scripts/test_store_checks.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import add_locale_fallbacks  # noqa: E402
import check_no_downgrade as c  # noqa: E402

fails = 0


def ok(cond, msg):
    global fails
    print(("ok   " if cond else "FEHL ") + msg)
    if not cond:
        fails += 1


# Tag-Vergleich: echte Tag-Formen aus Apps/*/docker-compose.yml
ok(c.compare("2.5.3", "2.5.1") == -1, "2.5.3 -> 2.5.1 sinkt")
ok(c.compare("2.5.1", "2.5.3") == 1, "2.5.1 -> 2.5.3 steigt")
ok(c.compare("v3.3.1", "v2.7.2") == -1, "v3.3.1 -> v2.7.2 sinkt (Immich-Fall)")
ok(c.compare("0.31.0", "0.28.0") == -1, "0.31.0 -> 0.28.0 sinkt (Memos-Fall)")
ok(c.compare("1.27.3", "1.27.3") == 0, "gleicher Tag")
ok(c.compare("3.1.0-ls95", "3.1.0-ls94") == -1, "linuxserver-Zaehler ls95 -> ls94 sinkt")
ok(c.compare("1.6.0-r6", "1.6.0-r7") == 1, "Revision r6 -> r7 steigt")
ok(c.compare("9.4.0.1", "9.4.0") == "floating", "9.4.0.1 -> 9.4.0 kuerzer, nur Hinweis")
ok(c.compare("17.2-alpine", "17-alpine") == "floating", "17.2-alpine -> 17-alpine gleitend, nur Hinweis")
ok(c.compare("17-alpine", "16-alpine") == -1, "17-alpine -> 16-alpine sinkt")
ok(c.compare("0.6.1-dind-rootless", "0.6.0-dind-rootless") == -1, "act_runner 0.6.1 -> 0.6.0 sinkt")
ok(c.compare("latest", "1.0.0") is None, "latest nicht vergleichbar")
ok(c.compare("alpine", "alpine") is None, "alpine nicht vergleichbar")
ok(c.compare("8", "8") == 0, "mysql 8 -> 8 gleich")
ok(c.compare("1.0.0-alpine", "1.0.0-debian") is None, "andere Nachsilbe nicht vergleichbar")
ok(c.split_ref("nginx:alpine@sha256:0530") == ("nginx", "alpine"), "Digest abgetrennt")
ok(c.split_ref("127.0.0.1:5000/app:1.0") == ("127.0.0.1:5000/app", "1.0"), "Registry mit Port")
ok(c.split_ref("127.0.0.1:5000/app") == ("127.0.0.1:5000/app", None), "Registry mit Port, ohne Tag")


def run(local_images, published_images, allow=()):
    with tempfile.TemporaryDirectory() as d:
        app = Path(d) / "Demo"
        app.mkdir()
        svcs = "\n".join(f"  {s}:\n    image: {i}" for s, i in local_images.items())
        (app / "docker-compose.yml").write_text(f"services:\n{svcs}\nx-casaos:\n  id: io.example.demo\n")
        pub = None if published_images is None else {"services": {s: {"image": i} for s, i in published_images.items()}}
        return c.check(d, "https://example.invalid/store", set(allow), fetcher=lambda url: pub)


f, n = run({"app": "x/demo:1.0.0"}, {"app": "x/demo:1.1.0"})
ok(len(f) == 1 and "1.1.0 -> 1.0.0" in f[0], "Absenkung gegen Veroeffentlichung = Fehler")
f, n = run({"app": "x/demo:1.2.0"}, {"app": "x/demo:1.1.0"})
ok(f == [], "Anhebung = kein Fehler")
f, n = run({"app": "x/demo:1.0.0"}, None)
ok(f == [] and any("noch nicht" in x for x in n), "neue App = Hinweis")
f, n = run({"app": "y/demo:1.0.0"}, {"app": "x/demo:2.0.0"})
ok(f == [] and any("Repository" in x for x in n), "Repo-Wechsel = Hinweis")
f, n = run({"app": "x/demo:1.0.0"}, {"app": "x/demo:1.1.0"}, allow={"io.example.demo:app"})
ok(f == [] and any("ALLOW_DOWNGRADE" in x for x in n), "benannte Ausnahme greift")
f, n = run({"app": "x/demo:1.0.0", "db": "pg:16"}, {"app": "x/demo:1.0.0", "db": "pg:17"}, allow={"io.example.demo:app"})
ok(len(f) == 1 and "db" in f[0], "Ausnahme gilt nur fuer den benannten Dienst")

# Sprach-Overlays
with tempfile.TemporaryDirectory() as d:
    dist = Path(d)
    (dist / "apps" / "io.example.a").mkdir(parents=True)
    (dist / "store.json").write_text(json.dumps({"store_id": "io.example.store"}))
    (dist / "apps" / "io.example.a" / "meta.json").write_text(json.dumps({"id": "io.example.a", "title": "A"}))
    (dist / "store.fr_FR.json").write_text(json.dumps({"store_id": "io.example.store", "name": "Magasin"}))
    langs = dist / "langs.json"
    langs.write_text(json.dumps(["en_US", "de_DE", "fr_FR"]))
    rc = add_locale_fallbacks.main(dist, langs)
    ok(rc == 0, "Overlays: rc 0")
    ok(json.loads((dist / "store.de_DE.json").read_text()) == {"store_id": "io.example.store"}, "store.de_DE.json nur store_id")
    ok(json.loads((dist / "index.de_DE.json").read_text()) == {"apps": []}, "index.de_DE.json leer")
    ok(json.loads((dist / "apps/io.example.a/meta.de_DE.json").read_text()) == {"id": "io.example.a"}, "meta.de_DE.json nur id")
    ok(json.loads((dist / "store.fr_FR.json").read_text()).get("name") == "Magasin", "vorhandenes Overlay unangetastet")
    ok(not (dist / "store.en_US.json").exists(), "Standardsprache bekommt kein Overlay")

print(f"\n{fails} FEHLER" if fails else "\nalles ok")
sys.exit(1 if fails else 0)
