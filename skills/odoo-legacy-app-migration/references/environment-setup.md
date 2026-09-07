# Local Environment Setup for Odoo Multi-Version Testing

Concrete recipes referenced by the main skill. Resolve every path/version by
name against the actual repos involved — nothing here is a fixed machine
path.

## Python version per Odoo core version

| Odoo version | Python  | Notes |
|---|---|---|
| 12.0 – 14.0 | 3.7 | Last generation before Odoo dropped 3.6/3.7 support |
| 15.0 – 16.0 | 3.8 – 3.10 | |
| 17.0 | 3.10 | |
| 18.0 – 19.0 | 3.10 – 3.12 | |

Set up with `pyenv install <version>` once, then `pyenv local <version>`
inside the worktree you're testing.

## Worktrees, not branch-switching

```bash
# One worktree per Odoo core version under test
git -C /path/to/odoo worktree add /path/to/odoo-13.0 origin/13.0
git -C /path/to/odoo worktree add /path/to/odoo-14.0 origin/14.0

# If the ADDON repo also needs two branches checked out concurrently
# (testing 13.0 and 14.0 in the same session), it needs its own worktree too
git -C /path/to/my-addon worktree add /path/to/my-addon-14.0 work-14.0
```

Never test version B against a checkout that's still on version A's branch
just because it's "the same repo" — the addons-path will resolve to whatever
is actually on disk, not whatever you think is checked out. A single shared
checkout that you keep branch-switching will silently make one version's
server run the *other* version's code; that has already produced a
convincing false "Odoo core bug" that was only stale code on disk.

## macOS/arm64 pip substitutions (local testing only)

Old pinned `requirements.txt` files from Odoo 12–15 commonly fail to build on
Apple Silicon. These substitutions are safe for *local functional testing*
(they are not what ships) — on Linux CI these problems mostly don't exist,
see `github-actions-ci.md` instead.

```bash
python -m venv .venv
grep -vi -e '^gevent' -e '^vatnumber' -e '^Pillow' -e '^reportlab' -e '^psycopg2' \
  requirements.txt > /tmp/requirements-local.txt

.venv/bin/pip install "Pillow==9.5.0" "reportlab==4.0.4" "psycopg2-binary==2.9.9"
.venv/bin/pip install -r /tmp/requirements-local.txt
```

`gevent` and `vatnumber` are safe to drop entirely for `--test-enable
--stop-after-init` runs — gevent is only needed for the longpolling worker,
vatnumber for VAT number validation neither of which module-install tests
exercise.

## Running odoo-bin locally without tripping over yourself

```bash
odoo-bin \
  -d my_test_db \
  --addons-path=addons,/path/to/my-addon \
  -i module_a,module_b \
  --test-enable \
  --test-tags=/module_a,/module_b \
  --stop-after-init \
  --log-level=test \
  --http-port=8081 \
  --limit-memory-hard=0 --limit-memory-soft=0 \
  --limit-time-cpu=0 --limit-time-real=0
```

- `--http-port` MUST be explicit and distinct per concurrently-running
  version — the single most common cause of a "phantom bug" in this
  workflow is a stale server on the default port answering another
  version's HTTP test client.
- `--limit-*=0` flags avoid Linux-only resource-limit assumptions that
  otherwise crash immediately on macOS.
- Drop `--test-tags` for at least one full run per version to catch
  anything outside your own modules' test scope.

## Measuring real coverage

```bash
pip install coverage
coverage run --source=/path/to/my-addon --omit="*/tests/*" \
  odoo-bin -d my_test_db --addons-path=addons,/path/to/my-addon \
  -i module_a,module_b --test-enable --test-tags=/module_a,/module_b \
  --stop-after-init

coverage report --include="*/my-addon/*" -m
```

Read the `Missing` column. A `__manifest__.py` showing 0% is not a real gap
(manifests are read via `ast.literal_eval`, never executed as code) — ignore
those lines specifically, but treat every other 0%/partial line as a real
question: is this route/method/branch actually reachable, and if so, why
isn't a test reaching it?

## Restart the server after file or data changes

A running server does not see file or data changes made while it is already
up. Three separate traps, all fixed the same way:

- *Compiled asset bundles* (`web.assets_frontend`/`_lazy`/etc.) are cached as
  `ir.attachment` rows, computed once and not re-checked against the source
  `.js`/`.xml` on disk on every request. Edit a JS file, reload the page
  against an already-running server, and you're still looking at the old
  bundle. Templates loaded dynamically via `ajax.loadXML()` (not part of a
  bundle) don't have this problem — they're fetched fresh on every request,
  so if only *those* aren't updating, look elsewhere first.
- *Some core caches don't see writes from a second process on the same DB.*
  Using a separate `odoo-bin shell` to set up or tweak data (e.g. a website's
  config fields) while a web server is already running against that database
  can leave the server serving stale values for a while, even for plain,
  non-computed fields — not every cache invalidates on a bare ORM write from
  outside its own process.
- *Installing a system binary dependency* (e.g. `wkhtmltopdf`) after the
  server already started doesn't help until you restart it. Some availability
  checks run once at Python import time (module-level code, not per-request)
  and cache the result for the life of the process.

In all three cases: kill and restart the `odoo-bin` process. Don't spend time
proving *why* a specific value is stale — if you changed a file, installed a
binary, or wrote data through a different process than the one serving
requests, restart first and re-test before debugging further.

## Odoo 19 flipped the demo-data default

Odoo 19 changed `--without-demo`'s default from "none disabled" (demo data
loads by default in a new database) to `true` (demo data is not installed at
all unless requested). If your tests or fixtures rely on demo records (base's
demo partners/products, etc.), pass `--with-demo` explicitly on 19.0+ — both
locally and in CI — or they'll fail with a missing-xmlid error that looks
unrelated to the actual migration.

## Browser-script URL routing differs by version

`/odoo/...` paths (e.g. `/odoo/sales`, `/odoo/inventory/products`) exist only
on ~18.0+; on ≤17.0 they 404 — use the classic hash router there
(`/web#id=<id>&model=<model>&view_type=form`). A Playwright script or tour
reused across versions needs both navigation modes behind a version switch,
or the "bug" you're chasing is just a 404 page.

## zsh does not word-split unquoted variables

Unlike bash. A flag stored in a shell variable
(`PLAT="--platform linux/amd64"; docker run $PLAT ...`) arrives as ONE
malformed token and the command dies with a confusing "unknown flag" error.
Write flags inline, use arrays, or `${=VAR}` when scripting loops across
versions in the user's default shell.

## Docker-on-macOS gotchas (Colima)

- **Treat local Docker state as disposable across sessions.** A host reboot or VM
  restart (Colima/Docker Desktop) can wipe containers, anonymous-volume databases
  and even pulled images between sessions — keep every instance/DB reconstructible
  from the branch plus one scripted `docker run ... -i <modules>` command, and never
  store anything in a test DB you can't regenerate. A `--rm -d` container that
  crashes on boot removes itself *with its logs* — rerun it foreground with
  `--stop-after-init` to capture the actual error.
- Old `odoo:<version>` images (≤15.0) ship no arm64 manifest — add
  `--platform linux/amd64` (runs via QEMU emulation; noticeably slower, and
  running 3-4 emulated installs concurrently can multiply that: stagger them).
- If `docker` suddenly reports "cannot connect to the Docker daemon" at a
  `desktop-linux` socket that doesn't exist, the CLI context is pointing at an
  uninstalled/removed Docker Desktop — `docker context use colima` fixes it.
- The image's entrypoint translates `HOST`/`USER`/`PASSWORD` env vars into
  `--db_host`/`--db_user`/`--db_password` flags. Bypass the entrypoint (a
  custom `bash -c`, or `docker exec`) and that translation is gone — pass the
  `--db_*` flags explicitly in those cases.
