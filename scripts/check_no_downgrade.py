#!/usr/bin/env python3
"""Fail the build when an app would ship an older image tag than the published store.

Why (measured 2026-10-16 on ZimaOS v1.8.0): an app installed from this store
carries `x-casaos.id` + `repo_id` of the store. ZimaOS treats the store's
compose as the image target of such an app. When the store's tag is older
than the one running on a box, the image-drift redeploy sets the older tag;
Memos 0.31 → 0.28 then stops with "cannot downgrade schema version" (same as
Immich 3.3.1 → 2.7.2). So a tag in this store must never go down.

Compared against what users actually get: the compose published under
<base-url>/apps/<x-casaos id>/docker-compose.yml, not the previous commit.

Only unambiguous pairs are compared: same repository, tags of the form
[v]N(.N)*[suffix[N]] with the same suffix text. Everything else (latest, alpine,
new app, repo change, floating shorter tag like 17.2 → 17) is reported, not failed.

Escape hatch for a deliberate rollback: ALLOW_DOWNGRADE="<app-id>:<service>[,…]".

Usage: check_no_downgrade.py <Apps-dir> <published-base-url>
"""
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

TAG = re.compile(r"^v?(\d+(?:\.\d+)*)(?:([-._+]?[A-Za-z][A-Za-z-]*?)(\d*))?$")


def split_ref(ref):
    """'repo:tag@sha256:…' -> (repo, tag); tag None when absent."""
    ref = ref.split("@", 1)[0]
    head, _, tail = ref.rpartition(":")
    if head and "/" not in tail:
        return head, tail
    return ref, None


def parse_tag(tag):
    m = TAG.match(tag or "")
    if not m:
        return None
    nums = tuple(int(x) for x in m.group(1).split("."))
    suffix = m.group(2) or ""
    build = int(m.group(3)) if m.group(3) else -1
    return nums, suffix, build


def compare(old, new):
    """-1 new older, 0 same, 1 newer, None not comparable, 'floating' shorter prefix."""
    a, b = parse_tag(old), parse_tag(new)
    if a is None or b is None or a[1] != b[1]:
        return None
    if len(b[0]) < len(a[0]) and a[0][: len(b[0])] == b[0]:
        return "floating"
    width = max(len(a[0]), len(b[0]))
    ka = a[0] + (0,) * (width - len(a[0])) + (a[2],)
    kb = b[0] + (0,) * (width - len(b[0])) + (b[2],)
    return (kb > ka) - (kb < ka)


def images(compose):
    return {name: svc.get("image") for name, svc in (compose.get("services") or {}).items() if svc.get("image")}


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return yaml.safe_load(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def check(apps_dir, base_url, allow, fetcher=fetch, counts=None):
    failures, notes = [], []
    counts = {} if counts is None else counts
    counts.update(apps=0, services=0)
    for compose_file in sorted(Path(apps_dir).glob("*/docker-compose.yml")):
        local = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
        app_id = (local.get("x-casaos") or {}).get("id")
        if not app_id:
            failures.append(f"{compose_file}: x-casaos.id fehlt")
            continue
        published = fetcher(f"{base_url.rstrip('/')}/apps/{app_id}/docker-compose.yml")
        if published is None:
            notes.append(f"{app_id}: noch nicht veroeffentlicht - nichts zu vergleichen")
            continue
        old_imgs = images(published)
        counts["apps"] += 1
        for svc, ref in images(local).items():
            counts["services"] += 1
            if svc not in old_imgs:
                notes.append(f"{app_id}:{svc}: neuer Dienst")
                continue
            (orepo, otag), (nrepo, ntag) = split_ref(old_imgs[svc]), split_ref(ref)
            if orepo != nrepo:
                notes.append(f"{app_id}:{svc}: Repository {orepo} -> {nrepo}, nicht verglichen")
                continue
            c = compare(otag, ntag)
            if c == -1:
                key = f"{app_id}:{svc}"
                if key in allow:
                    notes.append(f"{key}: {otag} -> {ntag} ABGESENKT, per ALLOW_DOWNGRADE erlaubt")
                else:
                    failures.append(f"{key}: Tag sinkt {otag} -> {ntag} (veroeffentlicht ist {otag})")
            elif c is None:
                if otag != ntag:
                    notes.append(f"{app_id}:{svc}: {otag} -> {ntag} nicht vergleichbar")
            elif c == "floating":
                notes.append(f"{app_id}:{svc}: {otag} -> {ntag} gleitender kuerzerer Tag, bitte von Hand pruefen")
    return failures, notes


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    allow = {x.strip() for x in os.environ.get("ALLOW_DOWNGRADE", "").split(",") if x.strip()}
    counts = {}
    failures, notes = check(argv[1], argv[2], allow, counts=counts)
    for n in notes:
        print("  hinweis:", n)
    for f in failures:
        print("  FEHLER: ", f)
    total = len(list(Path(argv[1]).glob("*/docker-compose.yml")))
    print(f"downgrade check: {counts['apps']} von {total} Apps gegen die Veroeffentlichung verglichen, "
          f"{counts['services']} Dienste, {len(failures)} Fehler, {len(notes)} Hinweise")
    if total == 0:
        print("  FEHLER:  keine App gefunden - falscher Pfad?")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
