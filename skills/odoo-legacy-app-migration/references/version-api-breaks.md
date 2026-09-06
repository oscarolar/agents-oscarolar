# Odoo Core API Breaks by Version (13.0 → 19.0)

Field-tested catalog: every entry below broke a real, working module during an
actual migration, and was verified against the official `odoo:<version>` Docker
image's core source (not changelogs). Use it as a pre-flight checklist when
targeting a version: read the target's section *and* remember the breaks are
cumulative. When something here seems off for your target, re-verify the same
way this list was built:

```sh
docker run --rm odoo:<X.0> python3 -c \
  "import inspect, odoo.<module> as m; print(inspect.getsource(m.<Thing>))"
```

## 13.0

- Picking form: no more inline `<tree>` under `move_line_ids_without_package`
  (it points at the named view `stock.view_stock_move_line_detailed_operation_tree`
  via `tree_view_ref`) — xpaths into the inline tree silently stop matching.

## 14.0

- `res_groups_users_rel`: the named UNIQUE constraint became a bare PRIMARY
  KEY — hardcoded `DROP CONSTRAINT <name>` in migration SQL breaks. Look the
  real name up via `pg_constraint` instead of hardcoding it.
- `stock.move.line.onchange_product_id()` → `_onchange_product_id()`.
- Prefetching groups-restricted `res.users` fields (e.g. auth_totp's) re-enters
  `has_group()` mid-check — access-check helpers must not read
  `env.user.company_id` through the ORM (raw SQL or cached value instead), and
  must not call `with_user()` unconditionally when uid == current uid.

## 15.0

- The `web.assets_backend` template-inheritance XML mechanism for registering
  assets is gone → manifest `'assets'` key.
- **15.0 only**: legacy QWeb2 templates must be listed under `web.assets_qweb`,
  not `web.assets_backend` — otherwise "Template not found" as a client-side
  error dialog at first use, with a green install.
- `web.ListRenderer` no longer exists — a `require('web.ListRenderer')` crashes
  the whole module file at load time.
- `stock.move.onchange_product_id()` → `_onchange_product_id()`.

## 16.0

- `ir.rule.domain_get()` removed → `_where_calc()` + `_apply_ir_rules()` +
  `Query.get_sql()`.
- `Many2many.limit` field attribute removed (`getattr(self, 'limit', None)` if
  you must stay cross-version).
- `sale.order.line.product_id_change()` removed (replaced by computes).
- `sudo()` hard-asserts a bool — `sudo(user)` → `with_user(user)`.
- `Model.flush(fnames)` flushes the *whole* dirty cache and chokes on manually
  cached non-column fields → prefer `flush_recordset([...])`.
- OWL field widgets, 16.0 shape: `registry.category("fields").add(name, Class)`
  (the class directly), global `const { Component } = owl` (no `@odoo/owl`
  import), `usePopover()` no-args + `.add(target, Comp, props, opts)` per
  click, template roots need `owl="1"`.

## 17.0

- `odoo.define()` and the whole legacy JS framework (`web.AbstractField`,
  `web.field_registry`) removed — modules written on them never load, with no
  error visible outside the browser. 17.0 shape: `import { Component } from
  "@odoo/owl"`, registry entry is an object `{component, supportedTypes,
  extractProps}`, `usePopover(Component, opts)` once + `.open(target, props)`,
  `standardFieldProps` lost `value`/`update` (read `record.data[props.name]`).
- `api.Environment.manage()` removed; install/uninstall hooks unified to a
  single `env` argument (shim: `arg.cr if hasattr(arg, 'cr') else arg`).
- `attrs`/`states` view attributes removed → direct Python-expression
  attributes (`invisible="not some_field"`).
- `Model.flush()` removed entirely → `flush_model()` / `flush_recordset()`.
- `registry.clear_caches()` → `clear_cache()`; ormcache-decorated functions no
  longer expose `.clear_cache`.
- Manifest version string must start with the branch's own `major.minor` —
  install dies on "Invalid version" otherwise.

## 18.0

- `<tree>` renamed `<list>` throughout core views — `//tree/...` xpaths stop
  matching; field `mode="tree,kanban"` became `mode="list,kanban"`.
- `Query.get_sql()` and `_generate_order_by()` removed → `Query.from_clause` /
  `.where_clause` (SQL objects exposing `.code` + `.params`) and
  `_order_to_sql()`. Three traps inside this one:
  - `_order_to_sql()` returns the clause *without* the `ORDER BY` keyword
    (the old helper included it).
  - Resolving the order can **add a JOIN to the Query as a side effect**
    (e.g. ordering `res.users` by `name` joins `res_partner` via `_inherits`)
    — resolve order *before* reading `from_clause`, or the join is silently
    missing and postgres rejects the ORDER BY.
  - Ordering by a translated field now carries bind params (`->>%s` lang) —
    account for them, positioned after every other placeholder.
- `product.template.type` drops `'product'` → storable is `type='consu'` +
  `is_storable=True` (new stock field).
- `res.users.has_group()`/`_has_group()` drop `@api.model` → plain instance
  methods with `ensure_one()` + a "only your own user (or admin)" guard. An
  override that keeps `@api.model` breaks RPC dispatch: the client now sends a
  bound record id, which lands as an extra positional arg (`TypeError: takes 2
  positional arguments but 3 were given`) and crashes whole screens.
- Vendor image pip: `externally-managed-environment` → `--break-system-packages`.
- New `/odoo/...` URL routes (`/odoo/sales`, `/odoo/inventory/products`) exist
  from here on; on ≤17.0 they 404 — browser scripts need the `/web#` hash
  router there.

## 19.0

- Core split `odoo/models.py` (and friends) into the `odoo/orm/` package.
- `_where_calc()` / `_apply_ir_rules()` removed → `model._search(domain)` now
  returns a fully-built `Query` with the domain *and* the ir.rule security
  domain already baked into its WHERE clause.
- `ormcache_context` deprecated **and its compat shim is genuinely broken**
  (`keys` is never stored as `self.keys` → `AttributeError` the first time the
  decorator is exercised) → plain `ormcache` with explicit key expressions
  like `'self.env.context.get("lang")'`.
- `self._cr` / `self._uid` deprecated → `self.env.cr` / `self.env.uid`
  (loud DeprecationWarnings with stack traces on every use).
- `from odoo import SUPERUSER_ID` → `ImportError` (moved under `odoo/orm/`,
  no longer re-exported) — `api.SUPERUSER_ID` works on every version.
- `res.groups._check_one_user_type()` removed — the one-user-type constraint
  is enforced inside core's own group write path via a new `disjoint_ids`
  mechanism; explicit calls to it are dead code.
- `res.users.groups_id` → `group_ids` and `res.groups.users` → `user_ids`,
  **keeping the same relation table** (`res_groups_users_rel`) — an override
  still defined on the old names installs green and appears to work, while
  core reads/writes through the new fields and silently bypasses all of its
  logic. The only tell is a log warning like "Two fields (groups_id,
  group_ids) of res.users() have the same label".
- `stock.move.name` removed (there's a readonly `inventory_name`);
  `stock.move._onchange_product_id()` removed from core entirely
  (`stock.move.line`'s survives); `stock.picking`'s
  `move_ids_without_package` → `move_ids`.
- `--without-demo` defaults to on → pass `--with-demo` explicitly when tests
  or fixtures need demo data.
