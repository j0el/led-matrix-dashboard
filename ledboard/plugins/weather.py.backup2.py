import os
import time
from math import cos, pi, radians, sin

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
            "wind_deg": None,
            "updated": "",
            "icon_code": "01d",
            "moon_phase": None,
            "is_night": False,
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
        icon_code = weather_list[0].get("icon", "01d")

        self.state = {
            "temp": round(current.get("temp", 0)),
            "feels_like": round(current.get("feels_like", 0)),
            "desc": weather_list[0].get("main", "Unknown"),
            "humidity": current.get("humidity", "--"),
            "wind": round(current.get("wind_speed", 0)),
            "wind_deg": current.get("wind_deg"),
            "updated": time.strftime("%I:%M %p").lstrip("0"),
            "icon_code": icon_code,
            "moon_phase": today_daily.get("moon_phase"),
            "is_night": str(icon_code).endswith("n"),
        }

        super().refresh()

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

    def _load_fonts(self):
        return (
            self._load_first_font(11),  # time
            self._load_first_font(38),  # temp
            self._load_first_font(12),  # desc
            self._load_first_font(10),  # stats
        )

    def _draw_sun(self, draw, cx, cy, r):
        for i in range(8):
            angle = (pi / 4) * i
            x1 = cx + int(cos(angle) * (r + 3))
            y1 = cy + int(sin(angle) * (r + 3))
            x2 = cx + int(cos(angle) * (r + 7))
            y2 = cy + int(sin(angle) * (r + 7))
            draw.line((x1, y1, x2, y2), fill=(255, 210, 70), width=1)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 210, 70))

    def _draw_cloud(self, draw, x, y, fill=(185, 185, 185)):
        draw.ellipse((x + 1, y + 10, x + 15, y + 24), fill=fill)
        draw.ellipse((x + 11, y + 5, x + 29, y + 23), fill=fill)
        draw.ellipse((x + 24, y + 10, x + 38, y + 24), fill=fill)
        draw.rounded_rectangle((x + 6, y + 14, x + 34, y + 26), radius=3, fill=fill)

    def _draw_rain(self, draw, x, y):
        self._draw_cloud(draw, x, y, fill=(165, 165, 165))
        for px, py in [(11, 30), (21, 32), (31, 30)]:
            draw.line((x + px, y + py, x + px - 2, y + py + 7), fill=(90, 170, 255), width=1)

    def _draw_snow(self, draw, x, y):
        self._draw_cloud(draw, x, y, fill=(185, 185, 185))
        for px, py in [(11, 30), (21, 32), (31, 30)]:
            draw.line((x + px - 2, y + py, x + px + 2, y + py), fill=(220, 235, 255), width=1)
            draw.line((x + px, y + py - 2, x + px, y + py + 2), fill=(220, 235, 255), width=1)

    def _draw_thunder(self, draw, x, y):
        self._draw_cloud(draw, x, y, fill=(150, 150, 150))
        bolt = [
            (x + 18, y + 26),
            (x + 13, y + 36),
            (x + 20, y + 36),
            (x + 15, y + 45),
            (x + 27, y + 31),
            (x + 20, y + 31),
        ]
        draw.polygon(bolt, fill=(255, 220, 80))

    def _draw_fog(self, draw, x, y):
        self._draw_cloud(draw, x + 2, y + 4, fill=(160, 160, 160))
        for yy in [29, 35, 41]:
            draw.line((x + 4, y + yy, x + 38, y + yy), fill=(130, 130, 130), width=1)

    def _draw_moon(self, draw, cx, cy, r, phase, fill=(220, 220, 190)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
        p = 0.0 if phase is None else float(phase) % 1.0

        if p < 0.03 or p > 0.97:
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(120, 120, 110))
            draw.ellipse((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), fill=(20, 20, 20))
            return

        if 0.47 <= p <= 0.53:
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 150, 130))
            return

        waxing = p < 0.5
        fullness = p * 2 if waxing else (1 - p) * 2
        shadow_offset = max(1, int((1 - fullness) * r * 1.7))

        if waxing:
            shadow_box = (cx - r - shadow_offset, cy - r, cx + r - shadow_offset, cy + r)
        else:
            shadow_box = (cx - r + shadow_offset, cy - r, cx + r + shadow_offset, cy + r)

        draw.ellipse(shadow_box, fill=(20, 20, 20))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 150, 130))

    def _draw_condition_icon(self, draw, icon_code, x, y):
        code = str(icon_code or "01d")
        main = code[:2]
        is_night = code.endswith("n")

        if main == "01":
            if is_night:
                self._draw_moon(draw, x + 18, y + 18, 11, 0.15)
            else:
                self._draw_sun(draw, x + 20, y + 21, 10)
        elif main in {"02", "03", "04"}:
            if main == "02" and not is_night:
                self._draw_sun(draw, x + 13, y + 12, 6)
            elif main == "02" and is_night:
                self._draw_moon(draw, x + 13, y + 12, 7, 0.15)
            self._draw_cloud(draw, x + 2, y + 10)
        elif main in {"09", "10"}:
            self._draw_rain(draw, x + 1, y + 7)
        elif main == "11":
            self._draw_thunder(draw, x + 1, y + 7)
        elif main == "13":
            self._draw_snow(draw, x + 1, y + 7)
        elif main == "50":
            self._draw_fog(draw, x + 1, y + 7)
        else:
            self._draw_cloud(draw, x + 2, y + 10)

    def _draw_wind_arrow(self, draw, cx, cy, deg):
        if deg is None:
            return

        # OpenWeather wind_deg is the direction the wind comes FROM.
        # Rotate 180 so the arrow points where the wind is blowing TO.
        angle = radians((float(deg) + 180.0) % 360.0)

        shaft_len = 8
        head_len = 4
        spread = radians(28)

        tip_x = cx + int(round(cos(angle) * shaft_len))
        tip_y = cy + int(round(sin(angle) * shaft_len))
        tail_x = cx - int(round(cos(angle) * 3))
        tail_y = cy - int(round(sin(angle) * 3))

        left_x = tip_x - int(round(cos(angle - spread) * head_len))
        left_y = tip_y - int(round(sin(angle - spread) * head_len))
        right_x = tip_x - int(round(cos(angle + spread) * head_len))
        right_y = tip_y - int(round(sin(angle + spread) * head_len))

        draw.line((tail_x, tail_y, tip_x, tip_y), fill=(120, 180, 255), width=1)
        draw.line((tip_x, tip_y, left_x, left_y), fill=(120, 180, 255), width=1)
        draw.line((tip_x, tip_y, right_x, right_y), fill=(120, 180, 255), width=1)

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        font_time, font_temp, font_desc, font_stat = self._load_fonts()

        draw.rectangle((0, 0, width - 1, height - 1), outline=(30, 90, 170))

        updated_text = self.state["updated"]
        if updated_text:
            updated_bbox = draw.textbbox((0, 0), updated_text, font=font_time)
            updated_w = updated_bbox[2] - updated_bbox[0]
            draw.text((width - updated_w - 6, 3), updated_text, font=font_time, fill=(120, 120, 120))

        temp_text = f"{self.state['temp']}°"
        draw.text((8, 5), temp_text, font=font_temp, fill=(255, 220, 70))

        desc_text = str(self.state["desc"]).upper()
        if len(desc_text) > 8:
            desc_text = desc_text[:8]
        draw.text((10, 42), desc_text, font=font_desc, fill=(190, 190, 190))

        if self.state.get("is_night"):
            # Make the moon clearly visible and larger than before.
            moon_phase = self.state.get("moon_phase")
            if moon_phase is not None:
                self._draw_moon(draw, width - 70, 24, 13, moon_phase)
            self._draw_condition_icon(draw, self.state.get("icon_code", "01n"), width - 38, 12)
        else:
            self._draw_condition_icon(draw, self.state.get("icon_code", "01d"), width - 44, 10)

        stats_y = 52
        draw.text((8, stats_y), f"F{self.state['feels_like']}°", font=font_stat, fill=(165, 165, 165))
        draw.text((64, stats_y), f"H{self.state['humidity']}%", font=font_stat, fill=(165, 165, 165))
        draw.text((122, stats_y), f"W{self.state['wind']}", font=font_stat, fill=(165, 165, 165))

        # Tiny wind arrow beside the wind reading.
        self._draw_wind_arrow(draw, 182, 56, self.state.get("wind_deg"))

        return image
