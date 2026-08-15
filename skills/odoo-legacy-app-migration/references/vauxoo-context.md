# Vauxoo Context — git.vauxoo.com Migrations

Everything in this file applies ONLY when the migration targets a repo on
`git.vauxoo.com` (e.g. `vauxoo/apps`). It was distilled from the real
`partner_blacklist` 12.0→19.0 series (T#102982, MRs !433/!434/!469/!500-!504)
and the `website_sale_product_brands` 15.0→19.0 series (T#74313, MRs
!277/!472-!475), where every rule below caught a real failure or saved a
real round-trip.

## Commit / history discipline (owner's standing rule)

- **At most two commits per MR**: one `[MIG]`/`[ADD]`/`[IMP]` carrying the
  migration *including every follow-up fix of a fix*, and optionally one
  `[REF]` for pure lint/pipeline autofixes. Fold review fixes back into the
  migration commit and force-push (`--force-with-lease`); never leave a
  trail of `[FIX] ...` commits on a migration MR.
- Preserve the original author when squashing someone else's branch
  (`git commit --author "Name <email>"`).
- **Squash trap**: never `git reset --soft origin/X.0` on a branch cut from
  an old base — the resulting commit carries the *whole old tree* and
  silently reverts everything merged into `X.0` since (CONTRIBUTING,
  sibling modules' fixes...). The MR file count explodes (73 files instead
  of 30) and it is easy to miss. Rebuild instead: `git checkout -B <branch>
  origin/X.0 && git checkout <old-sha> -- <module_dir> && git commit`, then
  assert `git diff --name-only origin/X.0..HEAD | grep -v '^<module>/'` is
  empty **and** re-check the MR `diffs` endpoint after pushing.
- Direct pushes to stable branches are blocked repo-wide (protected
  branches `*`: push = No one, even for Owners). To land a "direct commit"
  (e.g. a CONTRIBUTING backport) use MR + immediate merge: `merge_method=ff`
  and no pipeline gate mean the fast-forward leaves exactly the cherry-pick
  as the branch tip, no merge commit. Cherry-pick with `-x` to keep the
  original sha and author.
- The API `merge` call can 405 for a few seconds after MR creation while
  GitLab computes mergeability — retry, don't assume it failed.
- Small helper the whole session relied on: `git worktree add` one worktree
  per version branch (`~/inst/.worktrees/<repo>-X.0`) so several docker
  instances can mount different branches simultaneously.

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
- **The `.po` hooks have two more opinions you only learn from a red job**:
  (a) any `msgstr` identical to its `msgid` (e.g. `"ID"`, demo "Lorem
  ipsum") gets emptied — never hand-fill translations that equal the source;
  (b) msgstrs longer than the wrap width must be written as `msgstr ""` +
  continuation line, exactly like `--i18n-export` emits them. If you fill a
  fresh `.po` by script, run `pre-commit-vauxoo` twice locally on EVERY
  branch before pushing — the same file passed on 16.0 and failed on
  17.0/18.0/19.0 because each branch's export produced a slightly different
  set of terms.
- `odoo_warnings` (allow_failure, shows the pipeline as "warning") greps
  the test log for `WARNING` lines. Recurring one: demo users declaring an
  HTML `signature` as `type="xml"` (deprecated since 16.0) — fix is
  `type="html"`; check EVERY module of the branch (`git grep 'signature"
  type="xml"' origin/X.0`), not only the one you migrated, and open one MR
  per warning branch.
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
  When exporting from a live DB you used for screenshots, first revert any
  test data you wrote on demo records — it leaks into `msgid`s (a brand
  description typed for a screenshot became a translatable term).
- **A migration MR of a module that never shipped as an app** (no tests, no
  `static/description`, no demo user, bare manifest) is not mergeable until
  it meets the full checklist — "it installs" is not the bar. Budget for:
  tests up to the coverage gate (model + `HttpCase` on the public page),
  `static/description` (index.html on the Vauxoo template + banner/icon/
  cover + feature SVGs + real screenshots per version), a rewritten
  `README.rst` (placeholder "Instructions" and 11.0 runbot links are review
  findings), full manifest keys and a translated `es.po`. Do it once on the
  lowest branch, then forward-port the same set — screenshots and `es.po`
  still get regenerated per version.
- **Validate the demo user's groups by actually running the flow over RPC
  as that user** (create the record, write the M2O on the target model,
  clean up), not by reading group names: "website designer" cannot write
  `product.template` on 15/16/17 (needs `sales_team.group_sale_manager`),
  while 18/19 have the smaller `product.group_product_manager`. Groups
  differ per version — the demo XML is per branch, not shared.
- Keep the demo user's group xmlids free of the substring `admin` if you
  can, or expect the App Deployer heuristic below to bite.

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
   Known heuristic bug (fix in app-deployer !6): `_is_admin_user_record`
   regex-matched the bare word `admin` anywhere in the demo `<record>`, so a
   custom group like `group_brand_admin` made the sync skip the demo user
   and create the `deploy.app` with `demo_login = False`. Until that MR is
   merged, verify `demo_login` right after each sync and `write` the
   credentials on the record if empty (that is the ONLY acceptable manual
   touch on `deploy.app`).
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
- Playwright against Odoo 17's login page: there are three
  `button[type=submit]` and the first is invisible, so `page.click(...)`
  hangs — submit with `page.press("input[name=password]", "Enter")`. On
  ≤17 navigate via `about:blank` → full URL (a hash-only `goto` + reload
  races the router and lands on Discuss). Odoo 18+ never reaches
  `networkidle` (open websocket) — wait for `load` + a selector instead.
- Odoo 19: `--i18n-export` is gone from the server CLI; use
  `odoo i18n loadlang -d <db> -l es` then `odoo i18n export -d <db> <module>
  -l es` (module BEFORE `-l`, which is `nargs+`), and bypass the docker
  entrypoint (`sh -c` + `PGHOST/PGUSER/PGPASSWORD`) because it injects
  server-only flags into any command starting with `odoo`.
- Shared local Postgres saturates around 8-10 concurrent Odoo instances
  (`FATAL: sorry, too many clients already`, blank backend with "Connection
  restored" toasts, bus 500s). Stop instances you are done with before
  starting the next version's; a "flaky" test run right after starting new
  containers is usually this, not the code.
