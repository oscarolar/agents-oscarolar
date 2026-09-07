# oscarolar-personal

Oscar's personal (GitHub) hub of [Claude Code](https://claude.com/claude-code) skills for Odoo module work on personal and legacy repos, packaged as a Claude Code plugin (marketplace `oscarolar-hub`).

## Installation

```text
/plugin marketplace add https://github.com/oscarolar/agents-oscarolar
/plugin install oscarolar-personal@oscarolar-hub
```

Skills become available under the `oscarolar-personal:` namespace (e.g. `oscarolar-personal:odoo-legacy-app-migration`). Claude Code auto-discovers every `skills/*/SKILL.md` — adding a skill later doesn't require touching this manifest.

## Repository structure

```text
oscarolar-personal/
├── .claude-plugin/        # Claude Code plugin manifest + self-marketplace
├── plugin.json            # Root manifest (kept in sync with .claude-plugin/plugin.json)
├── skills/                # One directory per skill: SKILL.md (+ evals/, references/)
└── .github/workflows/     # Lint + structural validation for this repo
```

## Governance: adding a skill

1. Directory under `skills/` using hyphens (`my-skill`, never `my_skill`).
2. `SKILL.md` with YAML frontmatter: exactly `name` and `description` (must start with "Use " and include a "Triggers" clause listing example phrasings), under 1024 characters total.
3. `evals/evals.json` with at least 2 realistic prompt/expected_output pairs.
4. No personal data, no hardcoded record IDs, no absolute machine paths — resolve everything by name at runtime.
5. Commit with a message explaining *why*, not just what changed.

## Skills

- [odoo-legacy-app-migration](skills/odoo-legacy-app-migration/SKILL.md) — migrate a personal or legacy Odoo module to newer major versions, one version branch at a time, verifying real installability and behavior instead of trusting manifest flags or changelogs; also covers GitHub Actions CI for an Odoo module.

## Author

Oscar Alcalá ([@oscarolar](https://github.com/oscarolar))
