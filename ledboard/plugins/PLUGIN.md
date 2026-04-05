# Plugin authoring guide

This project uses a simple plugin architecture for full-screen LED Matrix panels.

## Goal

A plugin is a Python class that:

- subclasses `BasePlugin`
- has a stable `name`
- optionally sets `refresh_seconds` and `display_seconds`
- updates its internal `state` in `refresh()`
- returns a `PIL.Image.Image` from `render(width, height)`

The app rotates between plugins automatically.

---

## Directory layout

Put plugin files in the `plugins/` directory.

Example:

```text
ledboard/
├── main.py
├── plugin_base.py
├── plugin_manager.py
├── matrix_config.py
└── plugins/
    ├── weather.py
    ├── calendar_today.py
    └── my_new_plugin.py
```

---

## Required structure

Every plugin file should define **one main plugin class** that:

- subclasses `BasePlugin`
- has a class name ending in `Plugin`
- lives in a `.py` file inside `plugins/`

Example skeleton:

```python
import time
from PIL import Image, ImageDraw, ImageFont

from plugin_base import BasePlugin


class MyNewPlugin(BasePlugin):
    name = "my_new_plugin"
    refresh_seconds = 300
    display_seconds = 12

    def __init__(self, app_context):
        super().__init__(app_context)
        self.state = {
            "message": "Loading...",
            "updated": "",
        }

    def refresh(self):
        # Fetch or compute data here
        self.state = {
            "message": "Hello world",
            "updated": time.strftime("%I:%M %p").lstrip("0"),
        }
        super().refresh()

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        font = ImageFont.load_default()

        draw.rectangle((0, 0, width - 1, height - 1), outline=(80, 80, 80))
        draw.text((6, 6), self.state["message"], font=font, fill=(255, 255, 255))
        draw.text((width - 40, 6), self.state["updated"], font=font, fill=(120, 120, 120))

        return image
```

---

## BasePlugin contract

`BasePlugin` currently provides:

- `name`
- `refresh_seconds`
- `display_seconds`
- `app_context`
- `last_refresh`
- `state`
- `should_refresh(now_ts)`
- `refresh()`

Your plugin should call:

```python
super().refresh()
```

at the end of its own `refresh()` method so the refresh timestamp updates correctly.

---

## app_context

Plugins receive `app_context` during construction.

Typical keys:

- `width`
- `height`

Example:

```python
panel_width = self.app_context["width"]
panel_height = self.app_context["height"]
```

---

## Rendering rules

### `render(width, height)` must:

- return a `PIL.Image.Image`
- draw the full screen every time
- avoid mutating shared global state
- handle missing data gracefully

### Recommended style for LED readability

- prefer large simple text
- avoid tiny details unless they are tested on the real matrix
- prefer short labels like `F`, `H`, `W`, `N`, `D`
- use strong contrast
- use 1 border rectangle if helpful
- truncate long text instead of cramming

### Keep animation lightweight

This project may run on a Raspberry Pi Zero 2 W, so:

- avoid heavy per-frame computation
- avoid repeated API calls in `render()`
- do network work in `refresh()`, not `render()`
- precompute wrapped or shortened text where practical
- use simple marquee logic only when needed

---

## Refresh vs render

### Use `refresh()` for:

- API calls
- file reads
- parsing
- selecting which data to display
- preparing cached text/state

### Use `render()` for:

- drawing pixels only
- simple animation based on cached state
- layout logic

Bad pattern:

```python
def render(...):
    requests.get(...)
```

Good pattern:

```python
def refresh(...):
    data = requests.get(...)

def render(...):
    draw text from self.state
```

---

## Fonts

Use fallback font loading so the plugin works on both macOS and Raspberry Pi.

Recommended helper:

```python
def _load_first_font(self, size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()
```

---

## Error handling

Plugins should fail cleanly.

Good approach:

- validate env vars in `__init__`
- raise readable exceptions in `refresh()`
- let `main.py` show the error screen

Example:

```python
if not resp.ok:
    raise RuntimeError(f"API error {resp.status_code}: {resp.text}")
```

---

## Environment variables

If your plugin uses secrets or config, read them from environment variables.

Example:

```python
self.api_key = os.environ["MY_API_KEY"]
```

Document the required variables in the plugin file and in project notes.

---

## Naming conventions

Recommended:

- file: `my_new_plugin.py`
- class: `MyNewPlugin`
- display name: `name = "my_new_plugin"`

The main loader will scan `plugins/` and auto-register classes that:

- are defined in the module itself
- subclass `BasePlugin`
- are not `BasePlugin`
- have class names ending in `Plugin`

---

## Simple checklist for a new plugin

Before handing over a new plugin, make sure it:

- imports `BasePlugin`
- subclasses `BasePlugin`
- calls `super().__init__(app_context)`
- calls `super().refresh()` at the end of `refresh()`
- returns a PIL image from `render()`
- uses lightweight rendering
- works without editing `main.py`
- lives in `plugins/`
- defines a class ending in `Plugin`

---

## Example prompt for future plugin work

When creating a new plugin, use this guide and ask for:

- plugin name
- data source / API
- required env vars
- layout description
- refresh interval
- display duration
- whether scrolling is allowed
- whether it must be Pi Zero friendly

Example request:

> Write a plugin called `stocks.py` with class `StocksPlugin`.  
> Use `BasePlugin`.  
> Refresh every 10 minutes.  
> Show 3 tickers with price and daily change.  
> Keep it readable on a 192x64 LED matrix.  
> Use font fallbacks for macOS and Raspberry Pi.  
> Do not require changes to `main.py`.

---

## Main loader assumptions

The auto-discovery main file expects:

- plugins in `plugins/*.py`
- plugin package import path like `plugins.weather`
- one or more classes ending with `Plugin`
- subclass of `BasePlugin`

If a file contains helper classes only, that is fine; it just will not be listed.

---

## Testing

Useful commands:

```bash
python main.py --help
python main.py
python main.py 1
python main.py 1 3
```

Where the numbers come from the dynamically generated plugin list.

---

## Notes for ChatGPT

When writing a new plugin for this project:

1. Do not require manual edits to `main.py`.
2. Put the plugin in `plugins/`.
3. Define a class ending in `Plugin`.
4. Subclass `BasePlugin`.
5. Keep rendering LED-friendly and lightweight.
6. Prefer full replacement files over partial snippets unless asked otherwise.
