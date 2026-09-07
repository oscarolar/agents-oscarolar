# Resuming a Multi-Version Migration in a Fresh Session

This skill triggers on the phrasings in the frontmatter, but a cold session
has no memory of prior version branches, PRs, or running instances — carry
that context explicitly. This works for any repo and any version range
(there's nothing 13.0/14.0/15.0-specific about the flow itself); fill in
the bracketed placeholders with your own repo path, version numbers, app
names, PR numbers and ports:

```text
Use the oscarolar-personal:odoo-legacy-app-migration skill to continue
migrating /path/to/my-addon-repo to Odoo <target>.0.

Context: <prev2>.0 (PR #<n>, branch work-<prev2>.0) and <prev1>.0
(PR #<n+1>, branch work-<prev1>.0) are already migrated following this
methodology, with instances running on localhost:<port1> and
:<port2> respectively. The apps are: app_a, app_b, app_c, app_d.

Create a work-<target>.0 branch from origin/<target>.0 (it exists, but
may have the same half-disabled-apps pattern earlier versions started
with). Per app: audit its real state on that branch (don't trust
`installable`), migrate/fix whatever's needed, port or add tests,
close coverage to 100% where reasonable, and verify with a real
browser (a JS tour by default, per the Verification Ladder) on more
than one page (not just the homepage). Add the Docker-based GitHub
Actions pipeline (odoo:<target>.0, workflow file named
tests-<target>.0.yml) same as on the prior versions. Open a PR without
merging directly, and leave the instance running on a port distinct
from every version already running when done.
```

This same template also covers the very first version of a migration
(drop the "Context" paragraph entirely — there's nothing prior to carry
forward) and a single-step next-version continuation (just one prior
version in "Context" instead of two).
