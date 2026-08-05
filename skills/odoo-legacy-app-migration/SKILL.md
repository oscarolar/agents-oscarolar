---
name: "odoo-legacy-app-migration"
category: "DevOps"
description: "Use this skill when you need to migrate a personal or legacy Odoo module across multiple major versions (e.g. 12.0 to 19.0), one version branch at a time, verifying real installability and behavior instead of trusting manifest flags or changelogs. Covers per-version environment setup (git worktrees, pyenv, macOS/arm64 dependency substitutions), a verification ladder (pre-commit, scoped and full test runs, measured coverage, real headless-browser checks), a CI pipeline template that runs inside the official odoo/<version> Docker image and reports both test results and coverage, a table of recurring bug classes found this way, and PR/MR discipline. Triggers on: 'migrate this module to Odoo', 'upgrade this addon to version', 'port this app to the next Odoo version', 'audit this module for version', 'set up CI for this Odoo module'."
last_validated: "2026-08-05"
---

# Skill: Odoo Legacy App Multi-Version Migration

## Golden Rule

**A manifest's `installable: True`, a changelog line, or a passing-looking install log is not verification.** The only thing that counts: it installs cleanly on a real local instance of the *target* Odoo version, its automated tests pass (and you read the log, not just the exit code), coverage is *measured* rather than assumed, and a real headless browser sees the feature working with zero console errors on more than one page.

This skill was distilled from a real 12.0 → 14.0 migration of four personal Odoo apps, where every rule below caught a real bug or wasted real time before it was written down.

## Migration Strategy — One Version at a Time

1. **Work from the existing remote branch for that version if one exists** (`git checkout -b work-X.0 origin/X.0`). Never discard history and rebuild from scratch unless the user explicitly asks for it. A prior migration attempt that looks abandoned (`installable: False`, modules missing entirely) is a signal to *re-audit*, not to assume it's unsalvageable — bulk "disable everything, sort it out later" commits are common and usually disabled things that actually work fine.
2. **Audit every app present on that branch, not just the ones you started with.** Real repos grow: new apps get added on later version branches, and existing apps gain features across versions (a field added in one version update might already exist, silently unwired, on an earlier branch too — check, don't assume the changelog note is where a feature actually started). Every app/feature gets the same rigor regardless of where it came from.
3. **Per app, per version:** check the real state (don't trust the flag) → if it already installs and passes tests, add coverage rather than re-touching working code → if it's broken/disabled/missing, migrate/fix it.
4. **Before migrating any feature, check whether the target Odoo core version already covers the same use case natively.** If it does, don't resurrect the old code — grep the target core for the equivalent field/mixin, document the native equivalent in the PR description, and drop the feature. (Real example: a "multi-logo-per-website" app became pointless once core Odoo shipped a native per-website `logo` field — that's almost certainly *why* the original author dropped it without a replacement.)
5. **Never merge the working branch directly into the version branch.** Push it and open a Draft PR/MR for review. Leave a real local instance running afterward (see "Verification Ladder" step 5) so the requester can test it themselves without re-running anything.

## Environment Setup

- **One git worktree per Odoo core version being tested** (`git worktree add ../odoo-X.0 origin/X.0`) so multiple versions' servers can run concurrently without branch-switching collisions.
- **If the addon repo itself needs a different branch checked out per core version being tested at the same time, it also needs its own worktree.** A single shared checkout that you keep branch-switching will silently make one version's server run the *other* version's code — this produced a false "Odoo core bug" that was actually just stale code from a different branch still on disk.
- **pyenv/venv per Python version** the target Odoo core needs (see `references/environment-setup.md` for the version matrix).
- **Old pinned dependencies fail to build on modern macOS/arm64 toolchains** (Pillow, reportlab, psycopg2, gevent are the usual suspects). For *local* testing, don't fight the exact pin: install a newer version of just that package (prefer wheels over source builds — e.g. `Pillow==9.5.0`, `reportlab` unpinned, `psycopg2-binary`) and skip genuinely non-essential ones (`vatnumber`, `gevent`) for `--test-enable --stop-after-init` runs. **On Linux CI runners this problem mostly doesn't exist** — the original pins have prebuilt manylinux wheels; see the CI section below for why Docker sidesteps this entirely.
- **Always pass an explicit, version-distinct `--http-port`** to every `odoo-bin` invocation. Without it, if another version's server is already bound to the default port, your test's HTTP client silently talks to *that* server instead of your own — producing a "bug" that's actually a port collision, not your code. This is the single most misleading failure mode in this whole workflow: it produces a plausible, reproducible-looking symptom that has nothing to do with your changes.
- **Disable `--limit-memory-hard`/`--limit-memory-soft`/`--limit-time-cpu`/`--limit-time-real` locally** on macOS — they assume Linux resource semantics and error out.

## Verification Ladder — Do All of These, In This Order, Per Version

1. **Lint clean.** Bootstrap `.pre-commit-config.yaml`/`.flake8`/`.pylintrc` from a reference OCA/Vauxoo repo of the *same Odoo-version generation* if one exists locally — copy period-appropriate config, not just the newest one. Modern lint suggestions can be flatly wrong for old Odoo APIs (e.g. `self.env._` doesn't exist before Odoo 17 — a pylint_odoo suggestion that *breaks at runtime* if blindly applied to a 13.0/14.0 branch). Verify any such suggestion against the actual target version's core before applying; if inapplicable, revert and justify a scoped `# pylint: disable=...` with a one-line comment citing why.
2. **Scoped test run.** `-i <modules> --test-enable --test-tags=/<module1>,/<module2>,...` on a *fresh* database — scope test-tags to just your modules for fast iteration.
3. **Full untagged run at least once.** No `--test-tags` — makes sure nothing else broke. Read the log for FAIL/ERROR lines specifically attributable to *your* modules; core Odoo's own meta-tests (tests that intentionally raise errors to verify the test runner's own error logging) and pre-existing environment gaps (missing JS test harness, substituted reportlab) are expected noise, not your bug.
4. **Measured coverage**, not a test count. `coverage run --source=<your modules> --omit=*/tests/* -- <odoo-bin invocation>` then `coverage report -m`. Read the *Missing* column and close real gaps with real tests — controller routes nobody calls, cron methods, exception branches, batch loops that no-op on an empty recordset. "I wrote N tests" is not coverage; the percentage and the missing-lines list are.
5. **Real headless-browser pass** (Playwright or equivalent) against a running instance: check console/page errors on *every* representative page — home **and** a listing/detail page, not just the homepage. A template injected via an xpath that only renders on `/` and silently vanishes on `/shop` is a real, seen-in-production bug class (see table below). Manually trigger the interactive path (click add-to-cart, submit a form) rather than only asserting on static HTML — a bound click handler that never actually fires under browser automation but works under a direct DOM event trigger is a tooling quirk, not a bug; don't let it become one by giving up on the check.
6. **Re-verify after every fix, against the original failing scenario.** A one-line change that "looks like" the fix (e.g. reformatting an XML comment because it seemed like the plausible cause) must be proven against the *exact* originally-failing page/action before it's called done. Don't declare victory on a plausible-sounding cause without reproducing the fix end-to-end.
7. **CI: run the same verification on every push, in Docker.** See below.

## CI Pipeline — GitHub Actions Inside the Official Odoo Image

If the user is on GitHub's free tier (most common for a personal repo), GitHub Actions is enough — no external CI needed. Two approaches were tried on this migration; only the second one is worth using:

- ❌ **Clone Odoo core fresh + `pip install -r requirements.txt` on every run.** Works (old pins do have Linux wheels), but slow, and fragile the moment any of those decade-old pins stop resolving.
- ✅ **Run the job inside the official `odoo:<version>` Docker Hub image.** It already has Odoo, every dependency, and `python3-pip` installed via its `.deb` package, with community addons bundled in. A run only needs to check out the repo, `python3 -m pip install coverage` (the image has no bare `pip` executable — only reachable via `python3 -m pip`, same for the `coverage` command afterward), and point `--addons-path` straight at the checkout. No separate core clone, no `requirements.txt` install, no macOS-only dependency substitutions to worry about (they were only ever needed on macOS/arm64 — the Debian-based image sidesteps the whole problem).

Key details that aren't obvious until you hit them:

- Use `container: {image: "odoo:X.0", options: "--user root"}` on the job — the image's default `odoo` user can't `pip install` system-wide.
- When the job itself runs in a container, service containers (Postgres) are reached **by their service name** (e.g. `postgres`), not `localhost` — that's how Actions networks containerized jobs together. Don't reuse a `localhost`-based Postgres config from a non-containerized job.
- `odoo-bin`'s own exit code is not reliable across versions for signaling test failures — grep the log for the same markers the local verification ladder reads by hand (`modules.module: Module .*: N failures, M errors` with N or M non-zero, `tests.runner: N failed, M error(s)`, or any `FAIL:` line) and `exit 1` explicitly if found.
- Publish the coverage report to the run's job summary (`>> $GITHUB_STEP_SUMMARY`, wrapped in a fenced code block) — visible in the Actions UI with zero extra services (Codecov etc.) needed.
- See `references/github-actions-odoo.yml` for a complete, copy-adjustable workflow.

## Common Bug Classes Found This Way

| Symptom | Real Cause | Fix |
|---|---|---|
| Feature works on `/` but nowhere else | Injected via a template/xpath that only applies to a subset of routes (e.g. `portal.frontend_layout`'s `//nav`, which some listing routes don't render through) | Move the injection to a point proven to render on every route (e.g. `web.layout`'s `<head>`) |
| `$ is not defined` (or similar) in the browser console | Inline `<script>` on `DOMContentLoaded` assumes jQuery/a lib is already loaded, but Odoo lazy-loads part of the asset bundle | Rewrite as a `publicWidget` — it only attaches once its declared dependencies are actually loaded |
| A "new feature" flag/field exists but never does anything on the frontend | The access-control method (e.g. `can_access_from_current_website`) still reads the *old* single-value field a mixin defines, while the app only ever populates the *new* multi-value field it added | Override the access method to check the new field |
| A `NameError` buried in an `except` clause that never seems to fire in normal use | Exception class referenced without being imported — only surfaces under the exact race condition the `except` exists to handle | Add the import; also check except-clause order (specific subclasses before their parent, e.g. `OperationalError` before `Error`, or the parent swallows everything first) |
| A modern lint suggestion breaks at runtime on an old branch | The suggested API was added in a *later* Odoo version than the branch targets | Verify the suggestion against the actual target version's core before applying; if inapplicable, revert with a justified, scoped disable comment |
| `.pyc`/`__pycache__` show up in a diff | The repo's `.gitignore` doesn't cover them (or only covers them going forward) | Add the standard ignore section, `git rm --cached` anything already tracked, and say so explicitly in the PR — it's a removal, not new junk |
| CI step fails with `pip: not found` (or similar) inside a vendor Docker image | The image only exposes `python3 -m pip`, not a bare `pip` executable | Invoke via `python3 -m pip` / `python3 -m coverage` instead of the bare command |
| A test passes locally but not in CI (or vice versa) with an identical assertion | Environment mismatch invisible from the assertion itself — e.g. a different demo dataset shape, a public/portal user lacking read access to a record the test created without publishing it (`website_published`), or a route requiring a parameter your test omitted | Reproduce the *exact* failing request/record state, don't just re-read the assertion; check auth/access rules and required params first |

## PR/MR Discipline

- Split commits by concern (tooling bootstrap / one commit per bug fixed / test coverage / CI), each message stating the user-visible symptom, the root cause, and how it was verified — not just what changed.
- Never push directly to the version branch; work branch → push → PR/MR, left open for review.
- After pushing, leave a real local instance of that version running (with the fixed modules installed) so the requester can test it themselves without re-running anything.
- If a fix turns out to be wrong or incomplete once verified further (it happens — see the bug table's "plausible-sounding cause" trap), say so plainly in a follow-up commit rather than quietly amending history.

## References

- `references/environment-setup.md` — concrete pyenv/worktree/pip-substitution recipes and the Odoo-version → Python-version matrix.
- `references/github-actions-odoo.yml` — a complete, copy-adjustable GitHub Actions workflow (Docker-based, tests + coverage).
