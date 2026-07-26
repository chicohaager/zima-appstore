# Lintuxer Apps — a third-party app store for ZimaOS

Apps that were installed on a real ZimaOS machine, started, and logged into
before they were listed here. Each app says what was measured and when.

## Add the store

ZimaOS → **App Store** → add a source, and paste:

```
https://chicohaager.github.io/zima-appstore/store.json
```

Or over the API, which is what the UI does underneath:

```bash
ZIMA=<zimaos-ip>
TOKEN=$(curl -s -X POST http://$ZIMA/v1/users/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOURUSER","password":"YOURPASSWORD"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["token"]["access_token"])')

curl -s -X POST -H "Authorization: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"https://chicohaager.github.io/zima-appstore/store.json"}' \
  "http://$ZIMA/v3/app_store/repo"
```

The token goes in **raw**, without `Bearer` — that is not a typo, ZimaOS answers
`401 invalid or expired jwt` if you prefix it.

Removing it again: `GET /v3/app_store/repo` lists the stores with their ids,
`DELETE /v3/app_store/repo/{id}` removes one. Our id is
`io.github.chicohaager.lintuxer-apps`.

## Why a `store.json` and not a zip

Until 2026-07-26 this store shipped as a zip — a plain GitHub source archive,
the shape the BigBear store uses. **That route is closed for new sources.**

Measured on 2026-07-26 against ZimaOS v1.7.0-beta1: the App Store UI adds a
source through `POST /v3/app_store/repo`, and with a zip URL it answers

```
HTTP 400   {"message":"Unsupported import method."}
```

The same endpoint with a v2 `store.json` URL answers `HTTP 200` and registers the
store with `version: v2`, `transport: http`.

The old `POST /v2/app_management/appstore?url=<zip>` still works and still puts
the app into `GET /v2/app_management/apps` — but the source does **not** appear in
`GET /v3/app_store/repo`, so the new App Store UI never lists it. Those are two
separate registries; the zip sources that are still visible in the UI (BigBear)
were carried over once, they are not something a new store can join.

So this store is now built to the v2 protocol and published as static files.
`.github/workflows/release-store.yml` runs the official
`IceWhaleTech/build-appstore-action` on every push to `main` and deploys the
generated `dist/` to the `gh-pages` branch, which GitHub Pages serves.

## What is verified, and what is not

Measured on 2026-07-26 against ZimaOS v1.7.0-beta1, on a ZimaCube (amd64):

* The published files are the ones clients read: `store.json` and `index.json`
  answer `200` from GitHub Pages, and so do the app's `docker-compose.yml`,
  `meta.json` and `assets/icon.png` — fetched cache-busted, not from a browser
  that might have held an older copy.
* `POST /v3/app_store/repo` with the `store.json` URL answers `200` and the
  store lands in `GET /v3/app_store/repo` as
  `io.github.chicohaager.lintuxer-apps`, `version: v2`, `transport: http`.
* The sync is clean: the service journal reports `indexed_docs: 1` and no failed
  resource. (Registering a large foreign v2 store on the same machine reported
  `required_failed=300` — so the counter does say something.)
* Each app record now names its store. `GET /v3/app_store/hub/app/search?keyword=ninja`
  returns Invoice Ninja with `repo_id: io.github.chicohaager.lintuxer-apps`.
  That is the field the flat v2 catalog never had, and the reason the grouping
  works now.
* ✅ **The App Store UI renders the store as its own group** — clicked through in
  the browser, German locale: under "Gemeinschaftsläden" the sidebar lists
  `bigbeartechworld` and `Lintuxer Apps`, the group page shows the German store
  description from `store-config.json`, and Invoice Ninja appears with its icon,
  version `5.13.26` and an install button. This was the open question in the zip
  era; it is answered, and the answer was the protocol, not the metadata.
* Not verified: installing Invoice Ninja **from the store tile** on this machine.
  The app itself was installed and logged into on 2026-07-24, but through the
  compose, not through this store entry.
* **App text is English, deliberately.** Title, tagline, description and install
  tips carry `en_US` and nothing else, so an app reads the same to everyone who
  finds this store. The store's own name and description stay localized in
  `store-config.json` — that is the shelf, not the goods on it.
* Loose end: our repo record reports `locales: []` where the official store
  reports 19. Nothing visibly depends on it, but it is not understood, so it is
  written down rather than glossed over.

## Layout

```text
Apps/<AppName>/
    docker-compose.yml   the app, with its x-casaos block — the only source of truth
    config.json          id, version and image; a leftover of the zip era,
                         only Invoice Ninja still carries one
category-list.json       the categories, taken from the official store
store-config.json        store identity: store_id, localized name and description
supported-languages.json locales the build may emit
scripts/build_dist.sh    the same build the CI runs, for local checking
.github/workflows/       validate on pull requests, publish to gh-pages on main
```

`dist/` is generated, never committed. What ZimaOS reads lives on the `gh-pages`
branch and is served at `https://chicohaager.github.io/zima-appstore`.

Build it yourself before pushing:

```bash
cp .env.example .env
./scripts/build_dist.sh          # writes ./dist
```

## Apps

| App | Version | Port | Verified |
| --- | --- | ---: | --- |
| [CasaDrop](Apps/CasaDrop/) | 2.4.2 | 8086 | 2026-07-26 on ZimaOS v1.7.0-beta1: installed from this exact file on a machine that had never run it, `healthy` after 14 s, `/healthz` returning `ok`, the setup page rendered in the browser, tile in the grid with the right logo. Mounts checked one by one: five host folders read-only, `/DATA/AppData` not among them. Removed again afterwards — container, data directory and port all gone |
| [Gitea](Apps/Gitea/) | 1.27.0 | 3020 | 2026-07-25 on ZimaOS v1.7.0-beta1: four containers, runner registers itself, a real Actions run green *and* one deliberately red (`conclusion: failure`), `actions/checkout@v4` and `actions/setup-node@v4` from the marketplace green. Isolation measured, not assumed: inside a job `docker ps -a` shows only the job's own container, and `docker version` reports the inner daemon |
| [Invoice Ninja](Apps/InvoiceNinja/) | 5.13.26 | 8012 | 2026-07-24 on ZimaOS v1.7.0-beta1: four containers up, app container `healthy`, `/health` returning `{"status":"ok"}`, tile in the grid, admin login through the browser to the dashboard |
| [NextExplorer](Apps/NextExplorer/) | 2.2.7 | 3000 | 2026-07-25 on ZimaOS v1.7.0-beta1: `running` after 18 s, `healthy`, no placeholder left in the environment. `GET /api/volumes` returned exactly the four mounted shares and `GET /api/browse/Media` listed the same entries as `ls` on the host — so it reads the share, not a cache. A folder created through the API appeared on the host with the ownership `PUID`/`PGID` asked for, and was removed again |
| [Pterodactyl](Apps/Pterodactyl/) | 1.14.1 | 8080 | 2026-07-24 on ZimaOS v1.7.0-beta1: panel and wings as one app, the node wires itself up, a Minecraft server actually started (`Done (5.404s)!`, confirmed from outside over the game protocol), then removed without trace |

Gitea ships here as the **isolated** variant: the runner has its own Docker
daemon, not the host's socket. The socket variant is a little simpler and was
measured just as thoroughly — but in it a `docker ps` inside a job listed all 21
containers of the host, and any workflow could stop or read them. That is a fine
trade to make on your own machine and a poor one to hand to strangers through a
store. Both files live in `~/dev/Appstore-Pakete/Gitea/`.

### Before you install

Every app's install form carries its own notes; these are the ones worth knowing
before you click.

**CasaDrop** prints a one-time setup token to its log and shows it nowhere else.
Without it you cannot create the administrator account:
`docker logs casadrop | grep "SETUP TOKEN"`.

**Gitea** needs `ROOT_URL`, `SSH_DOMAIN`, `DOMAIN` and the runner's
`GITEA_INSTANCE_URL` pointed at this machine's address. `GITEA_INSTANCE_URL` must
**not** stay `http://server:3000` — the runner hands that value to every job
container, and those run in a network where `server` does not resolve.

**Pterodactyl** wants its `APP_URL` and the wings token values reviewed; the
panel builds every link from them.

**Invoice Ninja** needs three values changed — the
app's install form exposes them:

* `APP_URL` — the address you browse to, including the port. Invoice Ninja builds
  PDF links, mail links and the client portal from it.
* `APP_KEY` — the one in the file is public, because this file is public:
  `docker run --rm invoiceninja/invoiceninja-debian php artisan key:generate --show`
* `IN_PASSWORD` — the first admin account, created once on the first start.

First start takes about 90 seconds *after* ZimaOS reports `running`: the app runs
its database migrations before it serves anything, and answers `502` until then.

## What is not here, and why

**ZFW** and **VM-Extras** cannot be app store apps. Both are **systemd-sysext
modules**: `zfw.raw` and `zima_vm_extras.raw` under `/var/lib/extensions`, merged
into `/usr` by `systemd-sysext`, running as host services (`zfw-ui.service`,
`zfw.service`, `zima-vm-extras.service`). Checked on a live host, not inferred
from the file names.

That is not a packaging gap, it is what they are. ZFW's own Dockerfile says so in
as many words: the image is a delivery vehicle, not a runtime — a ZFW inside a
container has no host systemd to arm its Safe-Apply dead-man with, so the one
promise the whole design rests on would silently not exist. VM-Extras drives
libvirt on the host for the same reason. Both install with their own
`install.sh`, and that is the honest way to ship them.

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

Push to `main` and the release workflow rebuilds `dist/` and pushes it to
`gh-pages`; ZimaOS picks the change up on its next sync of the store. Watch it
with `gh run list -R chicohaager/zima-appstore`.

Nothing goes into this store that was not installed and opened once. If the entry
does not say what was verified and on which version, it is not ready.
