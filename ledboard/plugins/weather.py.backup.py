import os
import time
from math import cos, pi, sin

import requests
from PIL import Image, ImageDraw, ImageFont

from plugin_base import BasePlugin


class WeatherPlugin(BasePlugin):
    name = "weather"
    refresh_seconds = 600
    display_seconds = 12

    def __init__(self, app_context):
        super().__init__(app_context)
        self.api_key = os.environ["OPENWEATHER_API_KEY"]
        self.lat = os.environ["OPENWEATHER_LAT"]
        self.lon = os.environ["OPENWEATHER_LON"]

        self.state = {
            "temp": "--",
            "feels_like": "--",
            "desc": "Loading",
            "humidity": "--",
            "wind": "--",
            "updated": "",
            "icon_code": "01d",
            "moon_phase": None,
        }

    def refresh(self):
        try:
            lat = float(self.lat)
            lon = float(self.lon)
        except ValueError:
            raise ValueError(f"Invalid coordinates: lat={self.lat!r}, lon={self.lon!r}")

        url = "https://api.openweathermap.org/data/3.0/onecall"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "imperial",
            # Keep daily so we can read moon_phase.
            "exclude": "minutely,alerts",
        }

        resp = requests.get(url, params=params, timeout=15)
        if not resp.ok:
            raise RuntimeError(f"OpenWeather error {resp.status_code}: {resp.text}")

        data = resp.json()
        current = data.get("current", {})
        weather_list = current.get("weather", [{}])
        daily = data.get("daily", [{}])
        today_daily = daily[0] if daily else {}

        self.state = {
            "temp": round(current.get("temp", 0)),
            "feels_like": round(current.get("feels_like", 0)),
            "desc": weather_list[0].get("main", "Unknown"),
            "humidity": current.get("humidity", "--"),
            "wind": round(current.get("wind_speed", 0)),
            "updated": time.strftime("%I:%M %p").lstrip("0"),
            "icon_code": weather_list[0].get("icon", "01d"),
            "moon_phase": today_daily.get("moon_phase"),
        }

        super().refresh()

    def _load_first_font(self, size):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _load_fonts(self):
        return (
            self._load_first_font(11),  # time/header
            self._load_first_font(34),  # temperature
            self._load_first_font(17),  # description
            self._load_first_font(10),  # stats
            self._load_first_font(9),   # moon label
        )

    def _draw_sun(self, draw, cx, cy, r):
        for i in range(8):
            angle = (pi / 4) * i
            x1 = cx + int(cos(angle) * (r + 3))
            y1 = cy + int(sin(angle) * (r + 3))
            x2 = cx + int(cos(angle) * (r + 8))
            y2 = cy + int(sin(angle) * (r + 8))
            draw.line((x1, y1, x2, y2), fill=(255, 210, 70), width=1)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 210, 70))

    def _draw_cloud(self, draw, x, y, scale=1.0, fill=(185, 185, 185)):
        r1 = int(6 * scale)
        r2 = int(8 * scale)
        r3 = int(6 * scale)
        base_h = int(8 * scale)

        draw.ellipse((x, y + 4, x + 2 * r1, y + 4 + 2 * r1), fill=fill)
        draw.ellipse((x + 8, y, x + 8 + 2 * r2, y + 2 * r2), fill=fill)
        draw.ellipse((x + 20, y + 4, x + 20 + 2 * r3, y + 4 + 2 * r3), fill=fill)
        draw.rounded_rectangle(
            (x + 4, y + 10, x + 30, y + 10 + base_h),
            radius=3,
            fill=fill,
        )

    def _draw_rain(self, draw, x, y, scale=1.0):
        self._draw_cloud(draw, x, y, scale=scale, fill=(170, 170, 170))
        drops = [(8, 24), (16, 26), (24, 24)]
        for dx, dy in drops:
            draw.line(
                (
                    x + int(dx * scale),
                    y + int(dy * scale),
                    x + int((dx - 2) * scale),
                    y + int((dy + 6) * scale),
                ),
                fill=(90, 170, 255),
                width=1,
            )

    def _draw_snow(self, draw, x, y, scale=1.0):
        self._draw_cloud(draw, x, y, scale=scale, fill=(185, 185, 185))
        flakes = [(9, 25), (17, 27), (25, 25)]
        for dx, dy in flakes:
            px = x + int(dx * scale)
            py = y + int(dy * scale)
            draw.line((px - 2, py, px + 2, py), fill=(210, 230, 255), width=1)
            draw.line((px, py - 2, px, py + 2), fill=(210, 230, 255), width=1)

    def _draw_thunder(self, draw, x, y, scale=1.0):
        self._draw_cloud(draw, x, y, scale=scale, fill=(155, 155, 155))
        bolt = [
            (x + int(16 * scale), y + int(21 * scale)),
            (x + int(12 * scale), y + int(30 * scale)),
            (x + int(18 * scale), y + int(30 * scale)),
            (x + int(14 * scale), y + int(38 * scale)),
            (x + int(24 * scale), y + int(26 * scale)),
            (x + int(18 * scale), y + int(26 * scale)),
        ]
        draw.polygon(bolt, fill=(255, 220, 80))

    def _draw_fog(self, draw, x, y, scale=1.0):
        self._draw_cloud(draw, x + 3, y + 2, scale=0.9 * scale, fill=(160, 160, 160))
        for yy in [24, 29, 34]:
            draw.line(
                (x + 2, y + int(yy * scale), x + int(34 * scale), y + int(yy * scale)),
                fill=(130, 130, 130),
                width=1,
            )

    def _draw_icon(self, draw, icon_code, x, y):
        code = str(icon_code or "01d")
        main = code[:2]
        is_night = code.endswith("n")

        if main == "01":
            if is_night:
                self._draw_moon(draw, x + 16, y + 16, 10, 0.15, fill=(220, 220, 190))
            else:
                self._draw_sun(draw, x + 16, y + 16, 8)
        elif main in {"02", "03", "04"}:
            if main == "02" and not is_night:
                self._draw_sun(draw, x + 10, y + 11, 5)
            elif main == "02" and is_night:
                self._draw_moon(draw, x + 10, y + 11, 6, 0.15, fill=(210, 210, 180))
            self._draw_cloud(draw, x + 2, y + 10, scale=1.0, fill=(180, 180, 180))
        elif main in {"09", "10"}:
            self._draw_rain(draw, x + 1, y + 7, scale=1.0)
        elif main == "11":
            self._draw_thunder(draw, x + 1, y + 7, scale=1.0)
        elif main == "13":
            self._draw_snow(draw, x + 1, y + 7, scale=1.0)
        elif main == "50":
            self._draw_fog(draw, x + 1, y + 7, scale=1.0)
        else:
            self._draw_cloud(draw, x + 2, y + 10, scale=1.0, fill=(180, 180, 180))

    def _draw_moon(self, draw, cx, cy, r, phase, fill=(220, 220, 190)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)

        p = 0.0 if phase is None else float(phase) % 1.0

        if p < 0.03 or p > 0.97:
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 110))
            draw.ellipse((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), fill=(20, 20, 20))
            return

        if 0.47 <= p <= 0.53:
            return

        waxing = p < 0.5
        fullness = p * 2 if waxing else (1 - p) * 2
        shadow_offset = int((1 - fullness) * r * 1.8)

        if waxing:
            shadow_box = (cx - r - shadow_offset, cy - r, cx + r - shadow_offset, cy + r)
        else:
            shadow_box = (cx - r + shadow_offset, cy - r, cx + r + shadow_offset, cy + r)

        draw.ellipse(shadow_box, fill=(20, 20, 20))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 150, 130))

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        font_time, font_temp, font_desc, font_stat, font_small = self._load_fonts()

        draw.rectangle((0, 0, width - 1, height - 1), outline=(30, 90, 170))

        updated_text = self.state["updated"]
        if updated_text:
            updated_bbox = draw.textbbox((0, 0), updated_text, font=font_time)
            updated_w = updated_bbox[2] - updated_bbox[0]
            draw.text(
                (width - updated_w - 6, 3),
                updated_text,
                font=font_time,
                fill=(120, 120, 120),
            )

        temp_text = f"{self.state['temp']}°"
        draw.text((8, 14), temp_text, font=font_temp, fill=(255, 220, 70))

        self._draw_icon(draw, self.state.get("icon_code", "01d"), width - 44, 10)

        desc_text = str(self.state["desc"])
        draw.text((64, 22), desc_text, font=font_desc, fill=(220, 220, 220))

        moon_phase = self.state.get("moon_phase")
        if moon_phase is not None:
            self._draw_moon(draw, width - 20, 50, 8, moon_phase)
            draw.text((width - 41, 55), "moon", font=font_small, fill=(110, 110, 110))

        stats_y = 48
        draw.text(
            (8, stats_y),
            f"Feels {self.state['feels_like']}°",
            font=font_stat,
            fill=(175, 175, 175),
        )
        draw.text(
            (70, stats_y),
            f"Hum {self.state['humidity']}%",
            font=font_stat,
            fill=(175, 175, 175),
        )
        draw.text(
            (128, stats_y),
            f"Wind {self.state['wind']}",
            font=font_stat,
            fill=(175, 175, 175),
        )

        return image
