# Lintuxer App Store — a third-party app store for ZimaOS

Apps that were installed on a real ZimaOS machine, started, and logged into
before they were listed here. Each app says what was measured and when.

## Add the store

ZimaOS → **App Store** → add a source, and paste:

```
https://github.com/chicohaager/zima-appstore/archive/refs/heads/main.zip
```

Or over the API, which is what the UI does underneath:

```bash
ZIMA=192.168.1.100
TOKEN=$(curl -s -X POST http://$ZIMA/v1/users/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOURUSER","password":"YOURPASSWORD"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["token"]["access_token"])')

curl -s -X POST -H "Authorization: $TOKEN" \
  "http://$ZIMA/v2/app_management/appstore?url=https%3A%2F%2Fgithub.com%2Fchicohaager%2Fzima-appstore%2Farchive%2Frefs%2Fheads%2Fmain.zip"
```

The token goes in **raw**, without `Bearer` — that is not a typo, ZimaOS answers
`401 invalid or expired jwt` if you prefix it.

Removing it again: `GET /v2/app_management/appstore` lists the sources with their
ids, `DELETE /v2/app_management/appstore/{id}` removes one.

## Why a zip and not a `store.json`

The app store protocol has a v2 form where a store is a set of static files with
a `store.json` at the front. **ZimaOS v1.7.0-beta1 does not consume it.**
Measured on 2026-07-24: registering a valid v2 `store.json` answers `HTTP 200`,
the source never appears in the list, and the service journal says

```
failed to update appstore catalog   "error": "zip: not a valid zip file"
```

So this store ships as a zip — a plain GitHub source archive of this repository,
the same shape the BigBear store uses. `store-config.json` and
`supported-languages.json` are already here for the day a ZimaOS release reads v2.

## Layout

```text
Apps/<AppName>/
    docker-compose.yml   the app, with its x-casaos block
    config.json          id, version and image, for the store listing
category-list.json       the categories, taken from the official store
store-config.json        store identity (v2)
supported-languages.json locales (v2)
```

## Apps

| App | Version | Port | Verified |
| --- | --- | ---: | --- |
| [Invoice Ninja](Apps/InvoiceNinja/) | 5.13.26 | 8012 | 2026-07-24 on ZimaOS v1.7.0-beta1: four containers up, app container `healthy`, `/health` returning `{"status":"ok"}`, tile in the grid, admin login through the browser to the dashboard |

**Before you install Invoice Ninja**, change three values in the compose — the
app's install form exposes them:

* `APP_URL` — the address you browse to, including the port. Invoice Ninja builds
  PDF links, mail links and the client portal from it.
* `APP_KEY` — the one in the file is public, because this file is public:
  `docker run --rm invoiceninja/invoiceninja-debian php artisan key:generate --show`
* `IN_PASSWORD` — the first admin account, created once on the first start.

First start takes about 90 seconds *after* ZimaOS reports `running`: the app runs
its database migrations before it serves anything, and answers `502` until then.

## Adding an app

Apps here are generated and checked with [zimapp](https://github.com/chicohaager/zimapp):

```bash
python3 zimapp.py convert <upstream-compose-url> --name myapp --title "My App" \
    --category Productivity --app-id io.github.you.myapp -o Apps/MyApp/docker-compose.yml
python3 zimapp.py validate Apps/MyApp/docker-compose.yml
```

A listing needs `x-casaos.id` (reverse-domain), `version`, `title`, `icon`,
`category`, `main`, `index` and a string `port_map`. The official store's own
apps write the English locale key as `en_US`; both spellings work on install.

Nothing goes into this store that was not installed and opened once. If the entry
does not say what was verified and on which version, it is not ready.
