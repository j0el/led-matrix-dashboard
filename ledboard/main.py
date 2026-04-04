#!/usr/bin/env python3

import time
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from matrix_config import create_matrix, total_width, total_height
from plugin_manager import PluginManager
from plugins.weather import WeatherPlugin
from plugins.calendar_today import CalendarTodayPlugin


def load_error_font():
    try:
        return ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 12
        )
    except Exception:
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


def refresh_plugins_if_needed(plugins):
    now = time.time()
    for plugin in plugins:
        if plugin.should_refresh(now):
            try:
                plugin.refresh()
            except Exception as e:
                print(f"[{plugin.name}] refresh failed: {e}")


def main():
    load_dotenv()

    width = total_width()
    height = total_height()

    matrix = create_matrix()
    canvas = matrix.CreateFrameCanvas()

    app_context = {
        "width": width,
        "height": height,
    }

    plugins = [
        WeatherPlugin(app_context),
        CalendarTodayPlugin(app_context),
    ]

    for plugin in plugins:
        try:
            plugin.refresh()
        except Exception as e:
            print(f"[{plugin.name}] initial refresh failed: {e}")

    manager = PluginManager(plugins)

    while True:
        refresh_plugins_if_needed(plugins)

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

