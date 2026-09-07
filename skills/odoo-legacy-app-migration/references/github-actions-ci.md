# CI Pipeline — GitHub Actions Inside the Official Odoo Image

If the user is on GitHub's free tier (most common for a personal repo), GitHub Actions is enough — no external CI needed. Two approaches were tried on this migration; only the second one is worth using:

- ❌ **Clone Odoo core fresh + `pip install -r requirements.txt` on every run.** Works (old pins do have Linux wheels), but slow, and fragile the moment any of those decade-old pins stop resolving.
- ✅ **Run the job inside the official `odoo:<version>` Docker Hub image.** It already has Odoo, every dependency, and `python3-pip` installed via its `.deb` package, with community addons bundled in. A run only needs to check out the repo, `python3 -m pip install coverage` (the image has no bare `pip` executable — only reachable via `python3 -m pip`, same for the `coverage` command afterward), and point `--addons-path` straight at the checkout. No separate core clone, no `requirements.txt` install, no macOS-only dependency substitutions to worry about (they were only ever needed on macOS/arm64 — the Debian-based image sidesteps the whole problem).

Key details that aren't obvious until you hit them:

- Use `container: {image: "odoo:X.0", options: "--user root"}` on the job — the image's default `odoo` user can't `pip install` system-wide.
- When the job itself runs in a container, service containers (Postgres) are reached **by their service name** (e.g. `postgres`), not `localhost` — that's how Actions networks containerized jobs together. Don't reuse a `localhost`-based Postgres config from a non-containerized job.
- `odoo-bin`'s own exit code is not reliable across versions for signaling test failures — grep the log for the same markers the local verification ladder reads by hand (`modules.module: Module .*: N failures, M errors` with N or M non-zero, `tests.runner: N failed, M error(s)`, or any `FAIL:` line) and `exit 1` explicitly if found.
- Publish the coverage report to the run's job summary (`>> $GITHUB_STEP_SUMMARY`, wrapped in a fenced code block) — visible in the Actions UI with zero extra services (Codecov etc.) needed.
- **On newer `odoo:X.0` images (18.0/19.0+), `python3 -m pip install coverage` fails outright with `error: externally-managed-environment`.** These images moved to a Debian base with Python 3.12, which enforces PEP 668. Add `--break-system-packages` to the pip install step — it's safe here since the container is thrown away at the end of the job, not a persistent system Python.
- **Name the workflow file version-specifically from the very first commit** (`tests-X.0.yml`, never a shared `tests.yml` reused across branches). GitHub Actions caches and displays a run's workflow name keyed by file *path* — if every version branch reuses the same path, Actions can show a stale/wrong Odoo version name in the Actions UI for runs on a different branch, even though the underlying job is correct. This is easy to miss because the job itself passes; only the displayed name is wrong.

See `references/github-actions-odoo.yml` in this same directory for a
complete, copy-adjustable workflow implementing all of the above.
