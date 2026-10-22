#!/usr/bin/env python3
"""Write empty locale overlays for every supported language the build left out.

ZimaOS 1.8 asks for `store.<locale>.json`, `index.<locale>.json` and
`apps/<id>/meta.<locale>.json` in the user's UI language. The official
build-appstore-action only writes those files for locales that appear in the
app texts, and this store ships English texts only. So every German (French, …)
client got a 404 per file, logged by ZimaOS as
"background repo resource refresh failed" (measured 2026-10-16, ZimaOS v1.8.0).

The overlays written here carry no translation. They use exactly the shape the
action writes (`build_store_i18n_overlay`, `build_index_i18n_overlay_entry`,
`build_meta_i18n_overlay` in IceWhaleTech/build-appstore-action
scripts/build_appstore.py): only the id field, nothing to override, so the client
keeps the English base text. Files the action did write are never touched.

Usage: add_locale_fallbacks.py <dist-dir> <supported-languages.json>
"""
import json
import sys
from pathlib import Path

DEFAULT_LOCALE = "en_US"


def write_if_missing(path: Path, data) -> bool:
    if path.exists():
        return False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main(dist: Path, languages_file: Path) -> int:
    locales = [loc for loc in json.loads(languages_file.read_text(encoding="utf-8")) if loc != DEFAULT_LOCALE]
    store = json.loads((dist / "store.json").read_text(encoding="utf-8"))
    store_id = store["store_id"]
    app_dirs = sorted(p for p in (dist / "apps").iterdir() if (p / "meta.json").is_file())
    if not locales or not app_dirs:
        print(f"FEHLER: {len(locales)} Sprachen, {len(app_dirs)} Apps gefunden", file=sys.stderr)
        return 1
    written = 0
    for loc in locales:
        written += write_if_missing(dist / f"store.{loc}.json", {"store_id": store_id})
        written += write_if_missing(dist / f"index.{loc}.json", {"apps": []})
        for app in app_dirs:
            app_id = json.loads((app / "meta.json").read_text(encoding="utf-8"))["id"]
            written += write_if_missing(app / f"meta.{loc}.json", {"id": app_id})
    print(f"locale fallbacks: {written} files written for {len(locales)} locales x {len(app_dirs)} apps")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
