import os
import time

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
            "exclude": "minutely,daily,alerts",
        }

        resp = requests.get(url, params=params, timeout=15)
        if not resp.ok:
            raise RuntimeError(f"OpenWeather error {resp.status_code}: {resp.text}")

        data = resp.json()
        current = data.get("current", {})
        weather_list = current.get("weather", [{}])

        self.state = {
            "temp": round(current.get("temp", 0)),
            "feels_like": round(current.get("feels_like", 0)),
            "desc": weather_list[0].get("main", "Unknown"),
            "humidity": current.get("humidity", "--"),
            "wind": round(current.get("wind_speed", 0)),
            "updated": time.strftime("%I:%M %p").lstrip("0"),
        }

        super().refresh()

    def _load_fonts(self):
        try:
            font_header = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 12
            )
            font_temp = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 40
            )
            font_desc = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 18
            )
            font_stat = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", 11
            )
        except Exception:
            font_header = ImageFont.load_default()
            font_temp = ImageFont.load_default()
            font_desc = ImageFont.load_default()
            font_stat = ImageFont.load_default()

        return font_header, font_temp, font_desc, font_stat

    def render(self, width, height):
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        font_header, font_temp, font_desc, font_stat = self._load_fonts()

        draw.rectangle((0, 0, width - 1, height - 1), outline=(30, 90, 170))

        draw.text((4, 3), "WEATHER", font=font_header, fill=(110, 180, 255))

        updated_text = self.state["updated"]
        updated_bbox = draw.textbbox((0, 0), updated_text, font=font_header)
        updated_w = updated_bbox[2] - updated_bbox[0]
        draw.text(
            (width - updated_w - 6, 3),
            updated_text,
            font=font_header,
            fill=(120, 120, 120),
        )

        temp_text = f"{self.state['temp']}°"
        draw.text((6, 10), temp_text, font=font_temp, fill=(255, 220, 70))

        desc_text = str(self.state["desc"])
        desc_bbox = draw.textbbox((0, 0), desc_text, font=font_desc)
        desc_h = desc_bbox[3] - desc_bbox[1]
        draw.text((62, 20), desc_text, font=font_desc, fill=(220, 220, 220))

        stats_y = 47
        col1_x = 8
        col2_x = 72
        col3_x = 132

        draw.text(
            (col1_x, stats_y),
            f"Feels {self.state['feels_like']}°",
            font=font_stat,
            fill=(175, 175, 175),
        )
        draw.text(
            (col2_x, stats_y),
            f"Hum {self.state['humidity']}%",
            font=font_stat,
            fill=(175, 175, 175),
        )
        draw.text(
            (col3_x, stats_y),
            f"Wind {self.state['wind']}",
            font=font_stat,
            fill=(175, 175, 175),
        )

        return image

