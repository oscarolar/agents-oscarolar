"""Touch UI: a grid of buttons rendered with pygame.

pygame is used instead of a browser or a desktop toolkit so the deck can run on
Raspberry Pi OS Lite with no desktop at all: SDL talks to KMS/DRM directly and
reads the touchscreen through evdev. That keeps boot-to-usable at a few seconds
and leaves the Pi with nothing running that could steal focus from the deck.
"""

import logging
import os
import pathlib
import time

import pygame

from .config import DEFAULT_THEME

log = logging.getLogger(__name__)

SCREEN_SIZE = (800, 480)
HEADER_HEIGHT = 34
GRID_PADDING = 8
BUTTON_GAP = 8
BUTTON_RADIUS = 12
TOAST_SECONDS = 4.0

# A horizontal drag longer than this many pixels, completed quickly, is a page
# swipe rather than a button press.
SWIPE_MIN_DX = 70
SWIPE_MAX_DY = 70
SWIPE_MAX_SECONDS = 0.6

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
EMOJI_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
]


def parse_color(value, fallback):
    """Accept ``#rgb``, ``#rrggbb`` or a pygame colour name."""
    if not value:
        return fallback
    try:
        return pygame.Color(value)
    except ValueError:
        log.warning("unknown colour %r, falling back", value)
        return fallback


def _load_font(size, bold=False):
    for path in FONT_CANDIDATES:
        if pathlib.Path(path).is_file():
            font = pygame.font.Font(path, size)
            font.set_bold(bold and "Bold" not in path)
            return font
    font = pygame.font.SysFont(None, size)
    font.set_bold(bold)
    return font


def _load_emoji_font(size):
    """Colour-emoji fonts are bitmap-only and picky about size; failure is fine."""
    for path in EMOJI_FONT_CANDIDATES:
        if not pathlib.Path(path).is_file():
            continue
        for candidate_size in (size, 109):
            try:
                return pygame.font.Font(path, candidate_size)
            except (OSError, pygame.error):
                continue
    return None


def _wrap(font, text, max_width, max_lines=3):
    """Greedy word wrap, breaking over-long single words character by character."""
    if not text:
        return []
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= max_width or not current:
                current = candidate
                # A single word that still overflows gets hard-broken.
                while font.size(current)[0] > max_width and len(current) > 1:
                    cut = len(current) - 1
                    while cut > 1 and font.size(current[:cut])[0] > max_width:
                        cut -= 1
                    lines.append(current[:cut])
                    current = current[cut:]
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines[:max_lines]


class Deck:
    def __init__(self, config, runner, backlight, windowed=False):
        self.config = config
        self.runner = runner
        self.backlight = backlight
        self.windowed = windowed

        self.page_index = config.page_ids.index(config.start_page)
        self.pressed_index = None
        self.toast = None
        self.toast_until = 0.0
        self.last_input = time.monotonic()
        self.dimmed = False
        self.running = False

        self._icon_cache = {}
        self._touch_origin = None

        self._init_display()

        self.colors = {
            name: parse_color(config.theme.get(name), pygame.Color(fallback))
            for name, fallback in DEFAULT_THEME.items()
        }

        self.label_font = _load_font(20, bold=True)
        self.small_font = _load_font(15)
        self.header_font = _load_font(16, bold=True)
        self.emoji_font = _load_emoji_font(34)

    def _init_display(self):
        if not self.windowed:
            # Prefer KMS/DRM so the deck runs without a desktop; SDL falls back
            # to whatever driver is available if that fails (e.g. under labwc).
            os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
        pygame.display.init()
        pygame.font.init()

        flags = 0 if self.windowed else pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)
        except pygame.error as exc:
            if self.windowed or "SDL_VIDEODRIVER" not in os.environ:
                raise
            log.warning("kmsdrm unavailable (%s); retrying with the default driver", exc)
            del os.environ["SDL_VIDEODRIVER"]
            pygame.display.quit()
            pygame.display.init()
            self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)

        pygame.display.set_caption(self.config.title)
        pygame.mouse.set_visible(self.windowed)
        self.clock = pygame.time.Clock()

    @property
    def page(self):
        return self.config.pages[self.page_index]

    def button_rects(self):
        """Lay out the current page and yield ``(button, rect)`` pairs."""
        page = self.page
        top = HEADER_HEIGHT if self.config.show_header else 0
        area = pygame.Rect(
            GRID_PADDING,
            top + GRID_PADDING,
            SCREEN_SIZE[0] - 2 * GRID_PADDING,
            SCREEN_SIZE[1] - top - 2 * GRID_PADDING,
        )
        cell_width = (area.width - BUTTON_GAP * (page.columns - 1)) / page.columns
        cell_height = (area.height - BUTTON_GAP * (page.rows - 1)) / page.rows

        occupied = {b.position for b in page.buttons if b.position is not None}
        free_slots = (
            (row, column)
            for row in range(page.rows)
            for column in range(page.columns)
            if (row, column) not in occupied
        )

        pairs = []
        for button in page.buttons:
            slot = button.position if button.position is not None else next(free_slots, None)
            if slot is None:
                continue
            row, column = slot
            rect = pygame.Rect(
                round(area.x + column * (cell_width + BUTTON_GAP)),
                round(area.y + row * (cell_height + BUTTON_GAP)),
                round(cell_width),
                round(cell_height),
            )
            pairs.append((button, rect))
        return pairs

    def _icon_surface(self, button, max_size):
        """Render an icon: a PNG/JPG path if it resolves, otherwise emoji text."""
        cache_key = (button.icon, max_size)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        surface = None
        icon_path = pathlib.Path(button.icon).expanduser()
        if button.icon and icon_path.is_file():
            try:
                image = pygame.image.load(str(icon_path)).convert_alpha()
                scale = min(max_size / image.get_width(), max_size / image.get_height(), 1.0)
                surface = pygame.transform.smoothscale(
                    image,
                    (max(1, int(image.get_width() * scale)),
                     max(1, int(image.get_height() * scale))),
                )
            except pygame.error as exc:
                log.warning("cannot load icon %s: %s", icon_path, exc)
        elif button.icon and self.emoji_font is not None:
            try:
                rendered = self.emoji_font.render(button.icon, True, self.colors["text"])
                scale = min(max_size / rendered.get_height(), 1.0)
                surface = pygame.transform.smoothscale(
                    rendered,
                    (max(1, int(rendered.get_width() * scale)),
                     max(1, int(rendered.get_height() * scale))),
                )
            except pygame.error:
                surface = None

        self._icon_cache[cache_key] = surface
        return surface

    def draw(self):
        self.screen.fill(self.colors["background"])
        if self.config.show_header:
            self._draw_header()

        for index, (button, rect) in enumerate(self.button_rects()):
            self._draw_button(button, rect, pressed=index == self.pressed_index)

        if self.toast and time.monotonic() < self.toast_until:
            self._draw_toast(self.toast)

        pygame.display.flip()

    def _draw_header(self):
        page = self.page
        bar = pygame.Rect(0, 0, SCREEN_SIZE[0], HEADER_HEIGHT)
        pygame.draw.rect(self.screen, self.colors["button"], bar)

        title = self.header_font.render(page.name, True, self.colors["text"])
        self.screen.blit(title, (GRID_PADDING + 2, (HEADER_HEIGHT - title.get_height()) // 2))

        # One dot per page, the current one filled with the accent colour.
        dot_radius = 4
        spacing = 16
        total = len(self.config.pages)
        start_x = SCREEN_SIZE[0] - GRID_PADDING - (total - 1) * spacing - dot_radius
        for index in range(total):
            center = (start_x + index * spacing, HEADER_HEIGHT // 2)
            color = self.colors["accent"] if index == self.page_index else self.colors["muted"]
            pygame.draw.circle(self.screen, color, center, dot_radius)

    def _draw_button(self, button, rect, pressed):
        base = parse_color(button.color, self.colors["button"])
        fill = self.colors["button_pressed"] if pressed else base
        pygame.draw.rect(self.screen, fill, rect, border_radius=BUTTON_RADIUS)

        text_color = parse_color(button.text_color, self.colors["text"])
        inner_width = rect.width - 12

        icon = self._icon_surface(button, max_size=min(44, rect.height * 0.45))
        lines = _wrap(self.label_font, button.label, inner_width)
        line_height = self.label_font.get_linesize()

        block_height = len(lines) * line_height + (icon.get_height() + 6 if icon else 0)
        y = rect.y + (rect.height - block_height) // 2

        if icon:
            self.screen.blit(icon, (rect.centerx - icon.get_width() // 2, y))
            y += icon.get_height() + 6

        for line in lines:
            rendered = self.label_font.render(line, True, text_color)
            self.screen.blit(rendered, (rect.centerx - rendered.get_width() // 2, y))
            y += line_height

    def _draw_toast(self, message):
        rendered = self.small_font.render(message[:90], True, self.colors["text"])
        box = pygame.Rect(0, 0, rendered.get_width() + 24, rendered.get_height() + 14)
        box.midbottom = (SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] - 10)
        pygame.draw.rect(self.screen, pygame.Color("#8b2f2f"), box, border_radius=8)
        self.screen.blit(rendered, rendered.get_rect(center=box.center))

    def show_toast(self, message):
        self.toast = message
        self.toast_until = time.monotonic() + TOAST_SECONDS

    def change_page(self, page_id=None, offset=0):
        if page_id is not None:
            self.page_index = self.config.page_ids.index(page_id)
        else:
            self.page_index = (self.page_index + offset) % len(self.config.pages)
        self.pressed_index = None

    def _hit(self, position):
        for index, (button, rect) in enumerate(self.button_rects()):
            if rect.collidepoint(position):
                return index, button
        return None, None

    def _wake(self):
        """Any touch resets the idle timer and restores full brightness."""
        self.last_input = time.monotonic()
        if self.dimmed:
            self.backlight.set(100)
            self.dimmed = False
            return True
        return False

    def _apply_action(self, button):
        command = self.runner.run(button.action)
        if not command:
            return
        kind, value = command
        if kind == "page":
            self.change_page(page_id=value)
        elif kind == "error":
            self.show_toast(value)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # Only reachable with a keyboard attached to the Pi; handy for dev.
            self.running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            was_dimmed = self._wake()
            self._touch_origin = (event.pos, time.monotonic(), was_dimmed)
            if not was_dimmed:
                self.pressed_index, _ = self._hit(event.pos)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_release(event)

    def _handle_release(self, event):
        origin = self._touch_origin
        self._touch_origin = None
        pressed_index = self.pressed_index
        self.pressed_index = None
        self._wake()

        if origin is None:
            return
        (start_pos, started_at, was_dimmed) = origin

        dx = event.pos[0] - start_pos[0]
        dy = event.pos[1] - start_pos[1]
        elapsed = time.monotonic() - started_at

        if (
            abs(dx) >= SWIPE_MIN_DX
            and abs(dy) <= SWIPE_MAX_DY
            and elapsed <= SWIPE_MAX_SECONDS
            and len(self.config.pages) > 1
        ):
            self.change_page(offset=-1 if dx > 0 else 1)
            return

        # The touch that wakes a dimmed screen must not also fire a macro --
        # otherwise reaching past the deck starts your stream.
        if was_dimmed or pressed_index is None:
            return

        release_index, button = self._hit(event.pos)
        if release_index == pressed_index and button is not None:
            self._apply_action(button)

    def _update_idle(self):
        if self.config.dim_after_seconds <= 0 or self.dimmed:
            return
        if time.monotonic() - self.last_input >= self.config.dim_after_seconds:
            self.backlight.set(self.config.dim_level)
            self.dimmed = True

    def run(self):
        self.running = True
        self.backlight.set(100)
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)
                self._update_idle()
                self.draw()
                self.clock.tick(30)
        finally:
            self.backlight.set(100)
            pygame.quit()

