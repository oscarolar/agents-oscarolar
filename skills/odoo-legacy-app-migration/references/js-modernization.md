# JS Modernization During a Migration

Expansion of Migration Strategy rule 6 in SKILL.md: what "match what the
target version's own core already moved to" concretely means.

- Raw inline `<script>` + `DOMContentLoaded` (+ jQuery global) → `publicWidget` (frontend) or an OWL component (backend/interactive UI), matching whichever the target version's own core modules use for the same kind of surface.
- Legacy `odoo.define("module.name", function (require) {...})` module wrapper → the ES6 `/** @odoo-module **/` + `import`/`export` syntax once the target version supports it (Odoo 17+ mandates it; core drops `odoo.define` entirely there).
- Old `Widget`-based backend UI components → `OWL` components once the target version's core has moved to OWL for that same class of UI (started 15.0, mandatory by 17.0) — don't leave a `Widget` subclass in a codebase whose own core equivalent has already moved on.
- Direct jQuery DOM manipulation where the target version's core has already replaced the equivalent core widget with vanilla JS/OWL — prefer matching core's current approach over preserving the old jQuery call for its own sake.
- As with any other feature (see SKILL.md, Migration Strategy), check whether target core already exposes a tracking/analytics/UI hook natively before keeping a bespoke implementation of it.
- This is a "same rigor as everything else" rule, not a free pass to rewrite for style: only touch JS that's actually being migrated/fixed in this version's pass, and re-run the full Verification Ladder (lint, tests, coverage, real browser pass) against the rewritten version — a modernized widget that silently stops firing its event handler is exactly the kind of regression step 5 of the ladder exists to catch.
