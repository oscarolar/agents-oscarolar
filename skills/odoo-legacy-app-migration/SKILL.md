---
name: odoo-legacy-app-migration
description: "Use when migrating a personal or legacy Odoo module to one or more newer major versions (e.g. 12.0 to 19.0), auditing whether a module really works on a given version instead of trusting installable flags, or setting up GitHub Actions CI for an Odoo module. Triggers: 'migrate this module to Odoo X', 'upgrade this addon', 'port this app to the next version', 'audit this module for version X', 'set up CI for this Odoo module'. Not for repos on git.vauxoo.com alone; pair with the work plugin's vauxoo-apps-store-migration there."
---

# Odoo Legacy App Multi-Version Migration

## Overview

**A manifest's `installable: True`, a changelog line, or a passing-looking install log is not verification.** The only thing that counts: it installs cleanly on a real local instance of the *target* Odoo version, its automated tests pass (and you read the log, not just the exit code), coverage is *measured* rather than assumed, and a real headless browser sees the feature working with zero console errors on more than one page.

Last validated: 2026-09-07

## When to use

- Migrating a module across one or several major Odoo versions, one branch at a time.
- Auditing whether a module really works on a branch that claims it does.
- Reviving a legacy addon repo left half-disabled by an earlier attempt.
- Setting up GitHub Actions CI (tests + coverage) for an Odoo module.

**When NOT to use:** a repo on `git.vauxoo.com` alone — load the work plugin's App Store skill alongside this one there. Also not for a single-version bugfix that isn't a migration.

## Migration Strategy

1. **Work from the existing remote branch for that version if one exists** (`git checkout -b work-X.0 origin/X.0`); never rebuild from scratch unless asked. An abandoned-looking attempt (`installable: False`, modules missing) is a signal to *re-audit*: bulk "disable everything" commits usually disabled things that work fine.
2. **Audit every app on that branch, not just the ones you started with.** Apps appear on later branches and features land mid-series — a field added in one version may already exist, silently unwired, on an earlier one.
3. **Per app, per version:** check the real state (don't trust the flag) → if it installs and passes, add coverage rather than re-touch working code → if it's broken, disabled or missing, migrate/fix it.
4. **Before migrating any feature, check whether the target core already covers the use case natively.** If it does, document the native equivalent in the PR and drop the feature instead of resurrecting code that may override classes core no longer has.
5. **Never merge the working branch into the version branch directly.** Push it, open a Draft PR/MR, and leave a real local instance running so the requester can test without re-running anything.
6. **Modernize JS as part of the migration, don't port it as-is** — "it still works" isn't "what you'd write today". Match the pattern the target core uses for that surface (`references/js-modernization.md`); only touch JS actually being migrated this pass.
7. **`static/description/index.html` and its screenshots are the module's de-facto acceptance spec — read it FIRST and verify each documented behavior in a real browser.** Nothing in the pipeline touches this file, so it drifts silently: regenerate affected screenshots from that version's own instance (scriptable with Playwright), or state in the PR that nothing user-visible changed.
8. **Every app's manifest must price at €142.86 EUR or higher (`'price': ..., 'currency': 'EUR'`).** A floor, not a target: never lower an app already listed above it, only raise one missing or below, and keep it consistent across all version branches of the same app.
9. **Disabling a module (`installable: False`) is not a no-op for existing databases.** Any DB where it is already *installed* fails to load its registry on the next update, taking the instance down. Ship it with an uninstall path or the explicit understanding that existing installs must be removed, and drop the module from every CI `-i`/`--test-tags` list there.
10. **When a module's core mechanism can't honestly work on a newer version yet, disabling it beats shipping it broken.** Mark it `installable: False` with a manifest comment saying why and from which version; partial migration honesty is part of the deliverable.

## Verification Ladder

All of these, in order, per version.

1. **Lint clean.** Bootstrap `.pre-commit-config.yaml`/`.flake8`/`.pylintrc` from a reference OCA repo of the *same Odoo-version generation*, not the newest: modern suggestions can be flatly wrong on old APIs (`self.env._` doesn't exist before 17.0 and breaks at runtime). Verify each against the target core; revert the rest behind a justified `# pylint: disable=`.
2. **Scoped test run.** `-i <modules> --test-enable --test-tags=/<module1>,/<module2>` on a *fresh* database.
3. **Full untagged run at least once**, to catch what broke elsewhere. Read the log for FAIL/ERROR lines attributable to *your* modules; core's own meta-tests and pre-existing environment gaps are noise. When a run drags on, `grep -c` the suspect log line over the *whole* log each tick and alert on the delta — a slow loop stays under any per-window threshold while totaling tens of thousands.
4. **Measured coverage, not a test count.** `coverage run --source=<your modules> --omit=*/tests/* -- <odoo-bin ...>`, then `coverage report -m`: read the *Missing* column and close real gaps — uncalled routes, cron methods, exception branches, loops that no-op on an empty recordset.
5. **Real headless-browser pass against a running instance**, using Odoo's own JS tours by default (an `HttpCase` calling `self.start_tour(...)`) so it rides inside the test runs and CI you already have. Check home *and* a listing/detail page; traps in `references/browser-verification.md`.
6. **Audit separately any external config the app owns that references DOM selectors or URL patterns** (tag-manager export, browser-extension config). No Python/XML migration touches those, so they keep pointing at DOM that vanished two versions ago while every test passes. Rebuild them against the target's real DOM, preferring a stable value the app's JS already computes.
7. **Re-verify after every fix against the original failing scenario.** A change that "looks like" the fix must be proven on the *exact* originally-failing page/action.
8. **CI: the same verification on every push, in Docker** — `references/github-actions-ci.md`.

## PR/MR Discipline

- Split commits by concern (tooling bootstrap / one commit per bug fixed / test coverage / CI), each message stating the user-visible symptom, the root cause, and how it was verified — not just what changed.
- Never push directly to the version branch; work branch → push → PR/MR, left open for review.
- After pushing, leave a real local instance of that version running (with the fixed modules installed) so the requester can test it themselves without re-running anything.
- If a fix turns out to be wrong or incomplete once verified further, say so plainly in a follow-up commit rather than quietly amending history.

## Common mistakes

- Treating `installable: True`, a green exit code, or a plausible diff as proof instead of reading the log and clicking the feature.
- Branch-switching one checkout instead of a worktree per version, or omitting an explicit `--http-port` — `references/environment-setup.md`.
- Reloading the page instead of restarting the server after changing files or writing data from another process — same file.
- Reading "zero console errors" as "the feature works" — `references/browser-verification.md`.
- Search-and-replacing a core field name when core *replaced* the mechanism — `references/bug-classes.md`.
- Debugging a version break from scratch without checking `references/version-api-breaks.md` first.
- Reusing a shared `tests.yml` across branches, or expecting a bare `pip` in the image — `references/github-actions-ci.md`.

## References

- `references/environment-setup.md` — per-version setup, `odoo-bin` flags, coverage, restart / demo-data / URL-routing / zsh gotchas.
- `references/browser-verification.md` — tours, console reading, screencasts, Playwright fallback, traps.
- `references/js-modernization.md` — which legacy JS pattern maps to what in target core.
- `references/bug-classes.md` — symptom → cause → fix table of recurring bugs.
- `references/version-api-breaks.md` — version-keyed catalog (13.0→19.0) of core API removals/renames that broke real modules; check it BEFORE debugging a break from scratch.
- `references/github-actions-ci.md` — the Docker-based CI approach and its gotchas; `github-actions-odoo.yml` is the workflow itself.
- `references/resume-prompt.md` — template for resuming a migration in a fresh session.

For repos on git.vauxoo.com, the work plugin's `agents-oscarolar:vauxoo-apps-store-migration` skill layers the GitLab/App Store process on top of this one.
