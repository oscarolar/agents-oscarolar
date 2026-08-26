"""Load and validate ``deck.yaml``.

Validation is strict and eager: every button is checked at startup, including
its key combos, so a typo surfaces as a clear message on the console instead of
a button that silently does nothing three hours into a stream.
"""

import dataclasses
import pathlib

import yaml

from . import hidkeys

VALID_ACTION_TYPES = {
    "key", "text", "media", "sequence", "page", "shell", "brightness", "none",
}

DEFAULT_THEME = {
    "background": "#101216",
    "button": "#1e2530",
    "button_pressed": "#2f80ed",
    "text": "#eef2f7",
    "muted": "#8b97a8",
    "accent": "#2f80ed",
}


class ConfigError(ValueError):
    """Raised for any structural or semantic problem in the deck config."""


@dataclasses.dataclass
class Button:
    label: str
    action: dict
    icon: str = ""
    color: str = ""
    text_color: str = ""
    position: tuple = None  # (row, column), zero-based; None means "next free"


@dataclasses.dataclass
class Page:
    id: str
    name: str
    columns: int
    rows: int
    buttons: list

    @property
    def capacity(self):
        return self.columns * self.rows


@dataclasses.dataclass
class DeckConfig:
    title: str
    columns: int
    rows: int
    start_page: str
    pages: list
    theme: dict
    keyboard_device: str
    consumer_device: str
    dim_after_seconds: int
    dim_level: int
    show_header: bool

    def page(self, page_id):
        for page in self.pages:
            if page.id == page_id:
                return page
        raise ConfigError(f"no page with id {page_id!r}")

    @property
    def page_ids(self):
        return [page.id for page in self.pages]


def _require_int(value, field, minimum=1, maximum=12):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{field} must be an integer, got {value!r}")
    if not minimum <= value <= maximum:
        raise ConfigError(f"{field} must be between {minimum} and {maximum}, got {value}")
    return value


def _validate_action(action, where, page_ids):
    if not isinstance(action, dict):
        raise ConfigError(f"{where}: action must be a mapping, got {action!r}")

    action_type = action.get("type")
    if action_type not in VALID_ACTION_TYPES:
        raise ConfigError(
            f"{where}: unknown action type {action_type!r}. "
            f"Valid types: {', '.join(sorted(VALID_ACTION_TYPES))}."
        )

    try:
        if action_type == "key":
            hidkeys.resolve_combo(action.get("keys", ""))
        elif action_type == "media":
            hidkeys.resolve_consumer(action.get("key", ""))
        elif action_type == "text":
            if not isinstance(action.get("text"), str):
                raise ConfigError(f"{where}: 'text' action needs a 'text' string")
        elif action_type == "page":
            target = action.get("page")
            if target not in page_ids:
                raise ConfigError(
                    f"{where}: 'page' action targets unknown page {target!r}. "
                    f"Known pages: {', '.join(page_ids)}."
                )
        elif action_type == "shell":
            if not isinstance(action.get("command"), str) or not action["command"].strip():
                raise ConfigError(f"{where}: 'shell' action needs a non-empty 'command'")
        elif action_type == "brightness":
            if "level" not in action and "delta" not in action:
                raise ConfigError(f"{where}: 'brightness' action needs 'level' or 'delta'")
        elif action_type == "sequence":
            steps = action.get("steps")
            if not isinstance(steps, list) or not steps:
                raise ConfigError(f"{where}: 'sequence' action needs a non-empty 'steps' list")
            for index, step in enumerate(steps):
                _validate_step(step, f"{where} step {index + 1}")
    except hidkeys.UnknownKeyError as exc:
        raise ConfigError(f"{where}: {exc}") from exc


def _validate_step(step, where):
    if not isinstance(step, dict) or len(step) != 1:
        raise ConfigError(
            f"{where}: each step must be a single-entry mapping such as "
            "{key: ctrl+c}, {text: hello}, {media: mute} or {delay: 0.2}"
        )
    kind, value = next(iter(step.items()))
    if kind == "key":
        hidkeys.resolve_combo(value)
    elif kind == "media":
        hidkeys.resolve_consumer(value)
    elif kind == "text":
        if not isinstance(value, str):
            raise ConfigError(f"{where}: 'text' step must be a string")
    elif kind == "delay":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ConfigError(f"{where}: 'delay' step must be a non-negative number")
        if value > 10:
            raise ConfigError(f"{where}: 'delay' of {value}s is too long (max 10s)")
    else:
        raise ConfigError(
            f"{where}: unknown step {kind!r}; expected key, text, media or delay"
        )


def _build_button(raw, where, page_ids, columns, rows):
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: button must be a mapping, got {raw!r}")

    label = raw.get("label", "")
    if not isinstance(label, str):
        raise ConfigError(f"{where}: 'label' must be a string")

    action = raw.get("action", {"type": "none"})
    _validate_action(action, where, page_ids)

    position = raw.get("position")
    if position is not None:
        if not (isinstance(position, (list, tuple)) and len(position) == 2):
            raise ConfigError(f"{where}: 'position' must be [row, column]")
        row, column = position
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (row, column)):
            raise ConfigError(f"{where}: 'position' values must be integers")
        if not (0 <= row < rows and 0 <= column < columns):
            raise ConfigError(
                f"{where}: position [{row}, {column}] is outside the "
                f"{rows}x{columns} grid"
            )
        position = (row, column)

    return Button(
        label=label,
        action=action,
        icon=str(raw.get("icon", "")),
        color=str(raw.get("color", "")),
        text_color=str(raw.get("text_color", "")),
        position=position,
    )


def load(path):
    """Read, parse and validate a deck config file."""
    config_path = pathlib.Path(path).expanduser()
    if not config_path.is_file():
        raise ConfigError(f"config file not found: {config_path}")

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path}: invalid YAML ({exc})") from exc

    return from_mapping(data, source=str(config_path))


def from_mapping(data, source="<config>"):
    """Validate an already-parsed mapping. Kept separate so tests skip the disk."""
    if not isinstance(data, dict):
        raise ConfigError(f"{source}: top level must be a mapping")

    deck = data.get("deck") or {}
    if not isinstance(deck, dict):
        raise ConfigError(f"{source}: 'deck' must be a mapping")

    columns = _require_int(deck.get("columns", 5), "deck.columns")
    rows = _require_int(deck.get("rows", 3), "deck.rows")

    raw_pages = data.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ConfigError(f"{source}: 'pages' must be a non-empty list")

    page_ids = []
    for index, raw_page in enumerate(raw_pages):
        if not isinstance(raw_page, dict):
            raise ConfigError(f"{source}: page {index + 1} must be a mapping")
        page_id = raw_page.get("id")
        if not isinstance(page_id, str) or not page_id.strip():
            raise ConfigError(f"{source}: page {index + 1} needs a non-empty string 'id'")
        if page_id in page_ids:
            raise ConfigError(f"{source}: duplicate page id {page_id!r}")
        page_ids.append(page_id)

    pages = []
    for raw_page in raw_pages:
        page_id = raw_page["id"]
        page_columns = _require_int(
            raw_page.get("columns", columns), f"page {page_id}: columns"
        )
        page_rows = _require_int(raw_page.get("rows", rows), f"page {page_id}: rows")

        raw_buttons = raw_page.get("buttons") or []
        if not isinstance(raw_buttons, list):
            raise ConfigError(f"page {page_id}: 'buttons' must be a list")

        buttons = [
            _build_button(
                raw_button,
                f"page {page_id}, button {index + 1}",
                page_ids,
                page_columns,
                page_rows,
            )
            for index, raw_button in enumerate(raw_buttons)
        ]

        taken = [b.position for b in buttons if b.position is not None]
        if len(taken) != len(set(taken)):
            raise ConfigError(f"page {page_id}: two buttons share the same position")
        if len(buttons) > page_columns * page_rows:
            raise ConfigError(
                f"page {page_id}: {len(buttons)} buttons do not fit in a "
                f"{page_rows}x{page_columns} grid"
            )

        pages.append(
            Page(
                id=page_id,
                name=str(raw_page.get("name", page_id)),
                columns=page_columns,
                rows=page_rows,
                buttons=buttons,
            )
        )

    start_page = deck.get("start_page", pages[0].id)
    if start_page not in page_ids:
        raise ConfigError(
            f"{source}: deck.start_page {start_page!r} is not a known page id"
        )

    theme = dict(DEFAULT_THEME)
    raw_theme = deck.get("theme") or {}
    if not isinstance(raw_theme, dict):
        raise ConfigError(f"{source}: 'deck.theme' must be a mapping")
    theme.update({str(k): str(v) for k, v in raw_theme.items()})

    idle = deck.get("idle") or {}
    if not isinstance(idle, dict):
        raise ConfigError(f"{source}: 'deck.idle' must be a mapping")

    hid = deck.get("hid") or {}
    if not isinstance(hid, dict):
        raise ConfigError(f"{source}: 'deck.hid' must be a mapping")

    return DeckConfig(
        title=str(deck.get("title", "PiDeck")),
        columns=columns,
        rows=rows,
        start_page=start_page,
        pages=pages,
        theme=theme,
        keyboard_device=str(hid.get("keyboard", "/dev/hidg0")),
        consumer_device=str(hid.get("consumer", "/dev/hidg1")),
        dim_after_seconds=int(idle.get("dim_after_seconds", 120)),
        dim_level=max(0, min(100, int(idle.get("dim_level", 10)))),
        show_header=bool(deck.get("show_header", True)),
    )
