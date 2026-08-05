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
is actually on disk, not whatever you think is checked out.

## macOS/arm64 pip substitutions (local testing only)

Old pinned `requirements.txt` files from Odoo 12–15 commonly fail to build on
Apple Silicon. These substitutions are safe for *local functional testing*
(they are not what ships) — on Linux CI these problems mostly don't exist,
see the CI reference instead.

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
