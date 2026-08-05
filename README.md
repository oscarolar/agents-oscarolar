# Agents Oscarolar

Personal hub of [Claude Code](https://claude.com/claude-code) skills, packaged as a Claude Code plugin (marketplace `oscarolar-hub`). Follows the same structural conventions as Vauxoo's `agents-vauxoo` hub, so it installs the same way.

## Installation

```text
/plugin marketplace add https://github.com/oscarolar/agents-oscarolar
/plugin install agents-oscarolar@oscarolar-hub
```

Skills become available under the `agents-oscarolar:` namespace (e.g. `agents-oscarolar:odoo-legacy-app-migration`). Claude Code auto-discovers every `skills/*/SKILL.md` — adding a skill later doesn't require touching this manifest.

## Repository structure

```text
agents-oscarolar/
├── .claude-plugin/        # Claude Code plugin manifest + self-marketplace
├── plugin.json            # Root manifest (kept in sync with .claude-plugin/plugin.json)
├── skills/                # One directory per skill: SKILL.md (+ evals/, references/)
└── .github/workflows/     # Lint + structural validation for this repo
```

## Governance: adding a skill

1. Directory under `skills/` using hyphens (`my-skill`, never `my_skill`).
2. `SKILL.md` with YAML frontmatter: `name`, `category`, `description` (must start with "Use this skill when" and include a "Triggers on:" clause), `last_validated`.
3. `evals/evals.json` with at least 2 realistic prompt/expected_output pairs.
4. No personal data, no hardcoded record IDs, no absolute machine paths — resolve everything by name at runtime.
5. Commit with a message explaining *why*, not just what changed.

## Skills

- [odoo-legacy-app-migration](skills/odoo-legacy-app-migration/SKILL.md) — Use this skill when you need to migrate a personal or legacy Odoo module across multiple major versions, one version branch at a time, verifying real installability and behavior instead of trusting manifest flags or changelogs.

## Author

Oscar Alcalá ([@oscarolar](https://github.com/oscarolar))
