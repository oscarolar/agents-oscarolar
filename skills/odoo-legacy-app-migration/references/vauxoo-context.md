# Vauxoo Context — git.vauxoo.com Migrations

Everything in this file applies ONLY when the migration targets a repo on
`git.vauxoo.com` (e.g. `vauxoo/apps`). It was distilled from the real
`partner_blacklist` 12.0→19.0 series (T#102982, MRs !433/!434/!469/!500-!504),
where every rule below caught a real failure or saved a real round-trip.

## Repo / MR topology

- Upstream lives under `vauxoo/<repo>`; work branches live in the
  **`vauxoo-dev/<repo>` fork**. MR pipelines, jobs, traces and artifacts live
  in the **fork's** project (`projects/vauxoo-dev%2F<repo>/...`), not the
  upstream — querying the upstream for a job trace 404s.
- `glab` has no `--hostname` flag on this setup: prefix every call with
  `GITLAB_HOST=git.vauxoo.com`. Cross-project MRs are created via the API
  (`POST projects/vauxoo-dev%2F<repo>/merge_requests` with
  `target_project_id`), not `glab mr create`.
- Branch naming: `X.0-<topic>-<username>`. MR titles:
  `[MIG] <module>: Migration to X.0 T#<task>` — always carry the task number.
- Continue on top of a colleague's open MR by pushing to their fork branch
  (access allowing) instead of opening a rival MR; answer every open review
  thread with the commit sha that resolves it.
- Old superseded MRs of the same module: close them with a note pointing to
  the active series, after the user confirms.

## CI (the pipeline is the verification ladder's step 8 here — no GH Actions)

- Jobs: `precommit` (mandatory), `precommit_optional`, `odoo_test`,
  `build_docker`, `publish_coverage`, `odoo_warnings`. Per-branch env comes
  from `variables.sh` at the repo root (`MAIN_APP`, `ODOO_REPO=vauxoo/odoo`,
  `COVERAGE_MIN`, `PRECOMMIT_HOOKS_TYPE`, `PRECOMMIT_IS_PROJECT_FOR_APPS`).
- **`precommit` fails when the Autofix suite reports "Reformatted"** even if
  every mandatory check passes. Reproduce locally with `pre-commit-vauxoo`
  exporting the same env as `variables.sh` (`PRECOMMIT_HOOKS_TYPE=all`, plus
  `PRECOMMIT_IS_PROJECT_FOR_APPS=true` where the branch sets it), commit the
  autofixed files, and re-run until the second pass prints "Autofix checks
  Passed" (idempotence is the proof). Usual autofix offenders: prettier on
  legacy tour JS, `po-pretty-format` rewrapping long `es.po` msgstrs.
- **Your local pylint_odoo can be newer than CI's** and emit checks CI does
  not enforce (e.g. `category-allowed` on other modules' manifests). Before
  "fixing" anything outside your module, check whether the same check fails
  in the actual CI job trace — if it doesn't, leave it alone.
- `publish_coverage` is `allow_failure` on branches carrying repo-wide
  coverage debt: a red coverage job with a green pipeline is not your bug if
  your module reads 100% in the artifact's coverage.xml. Read the artifact
  (`GET .../jobs/<id>/artifacts`), don't guess.
- Every MR gets a runbot (`<build>-<iid>-<hash>.runbot.vauxoo.com`,
  admin/admin, single db `odoo`). A push triggers a fresh build — if you
  mutated the old instance while debugging (installing modules by hand), say
  so in the MR and re-verify on the new build.
- The apps-store linter (`PRECOMMIT_IS_PROJECT_FOR_APPS=true`, active on
  18.0+ branches of vauxoo/apps) additionally requires: manifests with a
  `price` must carry a `"support"` key (`support@vauxoo.com`), and flags
  module-level `_()` in favor of `self.env._` (valid from Odoo 18).
- The branch `build_docker` pushes
  `quay.io/vauxoo/vauxoo_apps:<MAIN_APP>-<X.0>-latest` — one image per
  branch, named after that branch's `MAIN_APP`, containing every module.
  That exact tag is what downstream tooling (App Deployer) expects.
- **12.0-era CI image trap**: `vauxoo/odoo-80-image-shippable-auto` ships
  OpenSSH 6.6 (Ubuntu 14.04) which cannot sign rsa-sha2 — GitHub rejects its
  SSH auth outright (RSA/SHA-1), so any `oca_dependencies.txt` entry pointing
  at `github.com` is dead on that branch. git.vauxoo.com's sshd still accepts
  the old client; mirroring the dependency there and repointing
  `oca_dependencies.txt` is the fix that doesn't require touching runner keys.

## CONTRIBUTING requirements that WILL come up in review

- `static/description/index.html` is the acceptance spec (general rule), but
  Vauxoo additionally requires: rich `README`, cover image + icon, price in
  EUR (no fixed floor — the listing price is a business decision; confirm the
  amount with the owner and keep it identical across every version branch),
  a non-admin demo user with minimum permissions declared in module demo
  data, and `live_test_url` set to the per-version shortener
  `https://www.vauxoo.com/r/<slug>_<XX0>` (e.g. `blacklist_170` for 17.0 —
  update it on EVERY version branch; a stale `_130` on a 17.0 branch is a
  review finding).
- `es.po` must be regenerated from a real instance of the target version
  (msgids are the DB-normalized shapes: `<t></t>`, `<br>`); reviewers check
  the `Project-Id-Version` header and exact msgid matching against the XML.

## Live-preview stack (post-merge, via odoo-mcp CLI)

Order matters: App Deployer first, shortener target second.

1. **App Deployer** (`deployer.vauxoo.com`, odoo-mcp profile `Deployer`):
   one `deploy.repository` record per repo+branch. Each record carries its
   own GitLab `token` (glpat) — a record created without one makes every API
   call 404; copy the token from a sibling record of the same repo.
   **Never create `deploy.app` records by hand**: call
   `deploy.repository.action_sync_apps` on the branch's repo record. It is
   idempotent (keyed on `repo_id =
   platform:host:project_path:branch:app_name`), lists the addon folders from
   the real branch, reads `functional_name` from the manifest, extracts the
   demo login/password from the module's demo XML, and computes
   `docker_image` from the branch's `MAIN_APP`. It can only see modules that
   are MERGED on the branch — run it per version after each merge, not before.
2. **Shortener** (`www.vauxoo.com`, odoo-mcp profile `Vauxoo`): Odoo link
   tracker. Create `link.tracker` with
   `url = https://deployer.vauxoo.com/?appname=<module>_<XX>`,
   `campaign_id=19` ("Promote Vauxoo Apss"), `source_id=214` ("Apps Store
   link"), `medium_id=1` ("Website"), then a `link.tracker.code` row with
   `code = <slug>_<XX0>` pointing at it. Verify with a curl: the code must
   301 to the deployer URL with UTMs appended. (Shorteners can be created
   before the merge; the deployer page only resolves once step 1 ran.)
3. `mexico/sync` (the monorepo concentrator) is NOT part of this flow —
   registering a repo there syncs ALL of its modules and needs explicit
   approval from the repo owner. Do not add entries on your own initiative.

## Review-verified behavior rules (found on this codebase, generic Odoo)

- A module whose documented flow lives under the Sales menu must depend on
  `sale_management`, not `sale`: core defines `sale.sale_menu_root` with
  `active="False"` inside `sale` (true on every version 12.0–19.0) and only
  `sale_management` activates it. With `sale` alone the module installs
  green, tests pass, and the documented menu path is unreachable on a fresh
  database — check it by installing ONLY the module on a fresh DB and
  querying `ir.ui.menu.active` for the root menu, not by clicking an
  already-provisioned instance where someone may have installed
  `sale_management` by hand.
