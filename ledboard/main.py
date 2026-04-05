#!/usr/bin/env python3

import importlib
import inspect
import pkgutil
import sys
import time

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from matrix_config import create_matrix, total_width, total_height
from plugin_base import BasePlugin
from plugin_manager import PluginManager
import plugins


def discover_plugins():
    discovered = []

    for module_info in pkgutil.iter_modules(plugins.__path__):
        module_name = module_info.name

        if module_name.startswith("_"):
            continue

        full_module_name = f"plugins.{module_name}"

        try:
            module = importlib.import_module(full_module_name)
        except Exception as e:
            print(f"[plugin-loader] failed importing {full_module_name}: {e}")
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BasePlugin:
                continue
            if not issubclass(obj, BasePlugin):
                continue
            if obj.__module__ != full_module_name:
                continue
            if not obj.__name__.endswith("Plugin"):
                continue

            display_name = getattr(obj, "name", None) or obj.__name__
            discovered.append((display_name, obj))

    discovered.sort(key=lambda item: item[0].lower())
    return discovered


PLUGIN_REGISTRY = discover_plugins()


def print_help():
    print("\nAvailable plugins:\n")
    if not PLUGIN_REGISTRY:
        print("  (none found)")
    else:
        for i, (name, cls) in enumerate(PLUGIN_REGISTRY, start=1):
            print(f"  {i}: {name}  [{cls.__name__}]")

    print("\nUsage:")
    print("  python main.py            # run all discovered plugins")
    print("  python main.py 1 3        # run selected plugins by number")
    print("  python main.py --help     # show this help\n")


def parse_selection(args):
    if not args:
        return [plugin_cls for _, plugin_cls in PLUGIN_REGISTRY]

    selected = []
    seen_indexes = set()

    for arg in args:
        if arg in ("-h", "--help"):
            print_help()
            sys.exit(0)

        if not arg.isdigit():
            print(f"Invalid argument: {arg}\n")
            print_help()
            sys.exit(1)

        idx = int(arg)
        if idx < 1 or idx > len(PLUGIN_REGISTRY):
            print(f"Invalid plugin number: {idx}\n")
            print_help()
            sys.exit(1)

        if idx not in seen_indexes:
            seen_indexes.add(idx)
            selected.append(PLUGIN_REGISTRY[idx - 1][1])

    return selected


def load_error_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, 12)
        except Exception:
            pass

    return ImageFont.load_default()


def render_error_screen(width, height, plugin_name, error_text):
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = load_error_font()

    draw.rectangle((0, 0, width - 1, height - 1), outline=(120, 40, 40))
    draw.text((6, 6), f"{plugin_name} error", font=font, fill=(255, 100, 100))

    msg = str(error_text).strip()
    if len(msg) > 70:
        msg = msg[:69] + "…"

    draw.text((6, 24), msg, font=font, fill=(190, 190, 190))
    return image


def refresh_plugins_if_needed(plugins_list):
    now = time.time()
    for plugin in plugins_list:
        if plugin.should_refresh(now):
            try:
                plugin.refresh()
            except Exception as e:
                print(f"[{plugin.name}] refresh failed: {e}")


def main():
    load_dotenv()

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print_help()
        return

    selected_plugin_classes = parse_selection(args)

    if not selected_plugin_classes:
        print("No plugins discovered.")
        print_help()
        return

    print("\nRunning plugins:")
    for plugin_cls in selected_plugin_classes:
        print(f"  - {plugin_cls.__name__}")
    print()

    width = total_width()
    height = total_height()

    matrix = create_matrix()
    canvas = matrix.CreateFrameCanvas()

    app_context = {
        "width": width,
        "height": height,
    }

    plugins_list = [plugin_cls(app_context) for plugin_cls in selected_plugin_classes]

    for plugin in plugins_list:
        try:
            plugin.refresh()
        except Exception as e:
            print(f"[{plugin.name}] initial refresh failed: {e}")

    manager = PluginManager(plugins_list)

    while True:
        refresh_plugins_if_needed(plugins_list)

        plugin = manager.current_plugin()

        try:
            image = plugin.render(width, height)
        except Exception as e:
            print(f"[{plugin.name}] render failed: {e}")
            image = render_error_screen(width, height, plugin.name, e)

        canvas.SetImage(image, 0, 0)
        canvas = matrix.SwapOnVSync(canvas)

        manager.tick_rotation()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
