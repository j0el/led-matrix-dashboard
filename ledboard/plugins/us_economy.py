"""
us_economy.py — US Economy Overview Plugin
===========================================

Optimised for a 192 × 64 LED matrix panel.

Layout (192 wide × 64 tall) — no title bar, no % signs:

  ┌──────────────────────────────────────────────────────────────────────────┐
  │  S&P 500      DOW            NASDAQ                                      │
  │  +1.2         -0.4           +0.8                                        │
  ├──────────────────────────────────────────────────────────────────────────┤
  │  CPI    JOBS   GDP    VIX    10YR                                        │
  │  3.2↑   4.1↓  +2.8   -5.3   4.32↑                                      │
  └──────────────────────────────────────────────────────────────────────────┘

All values are percentages — % sign omitted to save space.
VIX shown as daily % change vs prior close.

Trend arrows (↑ ↓) are drawn on level metrics that change slowly:
  CPI, JOBS, 10YR — compared against the prior FRED reading.
  GDP gets an arrow too (quarter-on-quarter direction).
  Stock/VIX % changes already encode direction via sign, so no arrow.

Macro label key:
  CPI   — CPI YoY inflation %              (FRED: CPIAUCSL, last 2 obs)
  JOBS  — Unemployment rate %              (FRED: UNRATE,   last 2 obs)
  GDP   — Real GDP growth, annualised %    (FRED: A191RL1Q225SBEA, last 2 obs)
  VIX   — CBOE VIX daily % change         (Yahoo: ^VIX)
  10YR  — 10-year Treasury yield %        (FRED: DGS10,    last 2 obs)

Market hours: NYSE Mon–Fri 09:30–16:00 ET, US federal holidays excluded.

Data sources:
  - Yahoo Finance : S&P 500, DOW, NASDAQ, VIX  (no key required)
  - FRED API      : CPI, JOBS, GDP, 10yr yield  (free key required)

Required environment variable:
  FRED_API_KEY   — https://fred.stlouisfed.org/docs/api/api_key.html

Optional:
  ECONOMY_REFRESH_SECONDS   (default: 600)
  ECONOMY_DISPLAY_SECONDS   (default: 15)
"""

import os
import time
import datetime
import urllib.request
import urllib.parse
import json

from PIL import Image, ImageDraw, ImageFont
from plugin_base import BasePlugin


# ---------------------------------------------------------------------------
# Market hours helper
# ---------------------------------------------------------------------------

def _is_market_open() -> bool:
    """Return True if NYSE is currently open (ET, Mon–Fri 09:30–16:00)."""
    import zoneinfo
    try:
        et = zoneinfo.ZoneInfo("America/New_York")
    except Exception:
        et = datetime.timezone(datetime.timedelta(hours=-5))

    now = datetime.datetime.now(tz=et)

    if now.weekday() >= 5:
        return False

    open_time  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    if not (open_time <= now < close_time):
        return False

    fixed_holidays = {(1,1),(6,19),(7,4),(12,25)}
    if (now.month, now.day) in fixed_holidays:
        return False

    def nth_weekday(year, month, weekday, n):
        d = datetime.date(year, month, 1)
        count = 0
        while True:
            if d.weekday() == weekday:
                count += 1
                if count == n:
                    return d
            d += datetime.timedelta(days=1)

    def last_weekday(year, month, weekday):
        d = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        while d.weekday() != weekday:
            d -= datetime.timedelta(days=1)
        return d

    y = now.year
    MO, TH = 0, 3
    floating = {
        nth_weekday(y, 1, MO, 3),
        nth_weekday(y, 2, MO, 3),
        last_weekday(y, 5, MO),
        nth_weekday(y, 9, MO, 1),
        nth_weekday(y, 11, TH, 4),
    }
    return now.date() not in floating


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "ledboard-economy/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _yahoo_pct(symbol: str) -> float | None:
    """Return today's % change for a Yahoo Finance symbol."""
    encoded = urllib.parse.quote(symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?interval=1d&range=2d"
    )
    try:
        data       = _fetch_json(url)
        meta       = data["chart"]["result"][0]["meta"]
        price      = meta.get("regularMarketPrice") or meta.get("chartPreviousClose", 0)
        prev_close = meta.get("chartPreviousClose", price)
        if prev_close:
            return (price - prev_close) / prev_close * 100
    except Exception:
        pass
    return None


def _fred_two(series_id: str, api_key: str) -> tuple[float | None, float | None]:
    """
    Return (latest, previous) observation values from FRED.
    Used to derive trend direction for level metrics.
    """
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}"
        f"&file_type=json&sort_order=desc&limit=2"
    )
    try:
        data = _fetch_json(url)
        obs  = data.get("observations", [])
        latest   = float(obs[0]["value"]) if len(obs) > 0 else None
        previous = float(obs[1]["value"]) if len(obs) > 1 else None
        return latest, previous
    except Exception:
        pass
    return None, None


def _fred_cpi_yoy_two(api_key: str) -> tuple[float | None, float | None]:
    """
    Return (latest YoY CPI, previous month's YoY CPI) so we can show trend.
    Fetches 14 observations: latest vs 12-months-ago, and month-prior vs its year-ago.
    """
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id=CPIAUCSL&api_key={api_key}"
        f"&file_type=json&sort_order=desc&limit=15"
    )
    try:
        data = _fetch_json(url)
        obs  = data.get("observations", [])
        if len(obs) >= 14:
            latest_yoy   = (float(obs[0]["value"]) - float(obs[12]["value"])) / float(obs[12]["value"]) * 100
            previous_yoy = (float(obs[1]["value"]) - float(obs[13]["value"])) / float(obs[13]["value"]) * 100
            return latest_yoy, previous_yoy
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Arrow drawing
# ---------------------------------------------------------------------------

# Threshold below which we consider a change "flat" (no arrow)
_FLAT_THRESHOLD = 0.001

def _trend(current: float | None, previous: float | None) -> str:
    """Return 'up', 'down', or 'flat' based on two consecutive readings."""
    if current is None or previous is None:
        return "flat"
    diff = current - previous
    if abs(diff) < _FLAT_THRESHOLD:
        return "flat"
    return "up" if diff > 0 else "down"


def _draw_arrow(draw: ImageDraw.ImageDraw, x: int, y: int, direction: str, color: tuple):
    """
    Draw a tiny 5×5 pixel up or down arrow at (x, y).
    direction: 'up' | 'down' | 'flat' (flat draws nothing)
    """
    if direction == "flat":
        return

    if direction == "up":
        # Triangle pointing up: tip at top-centre, base at bottom
        draw.polygon([
            (x + 2, y),        # tip
            (x,     y + 4),    # bottom-left
            (x + 4, y + 4),    # bottom-right
        ], fill=color)
    else:
        # Triangle pointing down: tip at bottom-centre, base at top
        draw.polygon([
            (x + 2, y + 4),    # tip
            (x,     y),        # top-left
            (x + 4, y),        # top-right
        ], fill=color)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

_FLASH_INTERVAL = 60
_FLASH_DURATION = 2


class UsEconomyPlugin(BasePlugin):
    name            = "us_economy"
    refresh_seconds = int(os.environ.get("ECONOMY_REFRESH_SECONDS", 600))
    display_seconds = int(os.environ.get("ECONOMY_DISPLAY_SECONDS", 15))

    # ── Palette ──────────────────────────────────────────────────────────────
    C_BG      = (0,   0,   0)
    C_BORDER  = (45,  45,  45)
    C_DIVIDER = (35,  35,  35)
    C_LABEL   = (90,  140, 210)
    C_UP      = (50,  210,  80)
    C_DOWN    = (220,  55,  55)
    C_NEUTRAL = (130, 130, 130)
    C_FLASH_1 = (200, 200, 200)
    C_OPEN    = (50,  210,  80)
    C_CLOSED  = (180, 100,  30)

    def __init__(self, app_context):
        super().__init__(app_context)
        self.fred_key = os.environ.get("FRED_API_KEY", "")
        if not self.fred_key:
            raise RuntimeError(
                "UsEconomyPlugin requires FRED_API_KEY. "
                "Free signup: https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self.state = {
            # current values
            "sp500":       None,
            "dow":         None,
            "nasdaq":      None,
            "cpi":         None,
            "jobs":        None,
            "gdp":         None,
            "vix":         None,
            "t10yr":       None,
            # previous values for trend arrows
            "cpi_prev":    None,
            "jobs_prev":   None,
            "gdp_prev":    None,
            "t10yr_prev":  None,
        }
        self._flash_shown_at    = 0.0
        self._last_flash_cycle  = 0.0

    # ── Data refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        self.state["sp500"]  = _yahoo_pct("^GSPC")
        self.state["dow"]    = _yahoo_pct("^DJI")
        self.state["nasdaq"] = _yahoo_pct("^IXIC")
        self.state["vix"]    = _yahoo_pct("^VIX")

        cpi, cpi_prev = _fred_cpi_yoy_two(self.fred_key)
        self.state["cpi"]      = cpi
        self.state["cpi_prev"] = cpi_prev

        jobs, jobs_prev = _fred_two("UNRATE", self.fred_key)
        self.state["jobs"]      = jobs
        self.state["jobs_prev"] = jobs_prev

        gdp, gdp_prev = _fred_two("A191RL1Q225SBEA", self.fred_key)
        self.state["gdp"]      = gdp
        self.state["gdp_prev"] = gdp_prev

        t10yr, t10yr_prev = _fred_two("DGS10", self.fred_key)
        self.state["t10yr"]      = t10yr
        self.state["t10yr_prev"] = t10yr_prev

        super().refresh()

    # ── Font loader ───────────────────────────────────────────────────────────

    def _font(self, size: int) -> ImageFont.ImageFont:
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

    # ── Format / colour helpers ───────────────────────────────────────────────

    @staticmethod
    def _fmt(val: float | None, decimals: int = 1, signed: bool = True) -> str:
        if val is None:
            return "N/A"
        if signed and val >= 0:
            return f"+{val:.{decimals}f}"
        return f"{val:.{decimals}f}"

    def _stock_color(self, pct):
        if pct is None or abs(pct) < 0.05: return self.C_NEUTRAL
        return self.C_UP if pct > 0 else self.C_DOWN

    def _cpi_color(self, val):
        if val is None: return self.C_NEUTRAL
        if val <= 2.5:  return self.C_UP
        if val >= 3.5:  return self.C_DOWN
        return self.C_NEUTRAL

    def _jobs_color(self, val):
        if val is None: return self.C_NEUTRAL
        if val <= 4.0:  return self.C_UP
        if val >= 5.5:  return self.C_DOWN
        return self.C_NEUTRAL

    def _gdp_color(self, val):
        if val is None or abs(val) < 0.1: return self.C_NEUTRAL
        return self.C_UP if val > 0 else self.C_DOWN

    def _vix_color(self, pct):
        if pct is None or abs(pct) < 0.5: return self.C_NEUTRAL
        return self.C_UP if pct < 0 else self.C_DOWN

    def _arrow_color(self, direction: str, good_is_up: bool) -> tuple:
        """Colour the arrow green/red based on whether up is good or bad."""
        if direction == "flat":
            return self.C_NEUTRAL
        rising = direction == "up"
        good   = rising if good_is_up else not rising
        return self.C_UP if good else self.C_DOWN

    # ── Render dispatcher ─────────────────────────────────────────────────────

    def render(self, width: int, height: int) -> Image.Image:
        now   = time.time()
        cycle = int(now // _FLASH_INTERVAL)
        if cycle != int(self._last_flash_cycle // _FLASH_INTERVAL):
            self._flash_shown_at  = now
            self._last_flash_cycle = now
        if now - self._flash_shown_at < _FLASH_DURATION:
            return self._render_flash(width, height)
        return self._render_data(width, height)

    # ── Flash screen ──────────────────────────────────────────────────────────

    def _render_flash(self, width: int, height: int) -> Image.Image:
        img  = Image.new("RGB", (width, height), self.C_BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, width - 1, height - 1), outline=self.C_BORDER)

        f1 = self._font(13)
        f2 = self._font(15)

        open_      = _is_market_open()
        line2_text = "Market open" if open_ else "Market closed"
        line2_col  = self.C_OPEN   if open_ else self.C_CLOSED

        total_h = 13 + 4 + 15
        start_y = (height - total_h) // 2

        t1 = "All values in percent"
        draw.text(((width - int(draw.textlength(t1, font=f1))) // 2, start_y),
                  t1, font=f1, fill=self.C_FLASH_1)
        draw.text(((width - int(draw.textlength(line2_text, font=f2))) // 2, start_y + 17),
                  line2_text, font=f2, fill=line2_col)
        return img

    # ── Data screen ───────────────────────────────────────────────────────────

    def _render_data(self, width: int, height: int) -> Image.Image:
        img  = Image.new("RGB", (width, height), self.C_BG)
        draw = ImageDraw.Draw(img)

        s = self.state

        f_slabel = self._font(11)
        f_svalue = self._font(19)
        f_mlabel = self._font(9)
        f_mvalue = self._font(15)

        draw.rectangle((0, 0, width - 1, height - 1), outline=self.C_BORDER)

        # ── Stocks row ────────────────────────────────────────────────────────
        col_w_stocks = (width - 8) // 3
        stock_metrics = [
            ("S&P 500", s["sp500"],  self._stock_color(s["sp500"])),
            ("DOW",     s["dow"],    self._stock_color(s["dow"])),
            ("NASDAQ",  s["nasdaq"], self._stock_color(s["nasdaq"])),
        ]
        for i, (label, val, color) in enumerate(stock_metrics):
            x = 4 + i * col_w_stocks
            draw.text((x, 2),  label,          font=f_slabel, fill=self.C_LABEL)
            draw.text((x, 14), self._fmt(val), font=f_svalue, fill=color)

        # Divider
        draw.line((2, 34, width - 3, 34), fill=self.C_DIVIDER)

        # ── Macro row — 5 columns with trend arrows ───────────────────────────
        #
        # Arrows are drawn as a tiny 5×5 triangle immediately to the right of
        # the value text.  The arrow sits at the vertical midpoint of the value.
        #
        # Trend direction semantics:
        #   CPI   up = inflation rising = bad  (good_is_up=False)
        #   JOBS  up = unemployment rising = bad (good_is_up=False)
        #   GDP   up = growth rising = good    (good_is_up=True)
        #   10YR  up = yields rising (neutral, shown grey always)
        #
        col_w_macro = (width - 8) // 5
        arrow_y_offset = 5   # pixels down from value_y to vertically centre the 5px arrow

        macro_metrics = [
            # (label, text, value_color, trend_direction, good_is_up)
            ("CPI",
             self._fmt(s["cpi"],   signed=False),
             self._cpi_color(s["cpi"]),
             _trend(s["cpi"],   s["cpi_prev"]),
             False),

            ("JOBS",
             self._fmt(s["jobs"],  signed=False),
             self._jobs_color(s["jobs"]),
             _trend(s["jobs"],  s["jobs_prev"]),
             False),

            ("GDP",
             self._fmt(s["gdp"],   signed=True),
             self._gdp_color(s["gdp"]),
             _trend(s["gdp"],   s["gdp_prev"]),
             True),

            ("VIX",
             self._fmt(s["vix"],   signed=True),
             self._vix_color(s["vix"]),
             "flat",   # VIX is already a % change — sign encodes direction
             True),

            ("10YR",
             self._fmt(s["t10yr"], decimals=2, signed=False),
             self.C_NEUTRAL,
             _trend(s["t10yr"], s["t10yr_prev"]),
             None),    # None = always neutral colour on arrow
        ]

        for i, (label, text, val_color, direction, good_is_up) in enumerate(macro_metrics):
            x        = 4 + i * col_w_macro
            value_y  = 46

            draw.text((x, 36), label, font=f_mlabel, fill=self.C_LABEL)
            draw.text((x, value_y), text, font=f_mvalue, fill=val_color)

            if direction != "flat":
                # Place arrow just after the value text
                text_w    = int(draw.textlength(text, font=f_mvalue))
                arrow_x   = x + text_w + 2
                arrow_y   = value_y + arrow_y_offset

                # Determine arrow colour
                if good_is_up is None:
                    arrow_col = self.C_NEUTRAL
                else:
                    arrow_col = self._arrow_color(direction, good_is_up)

                _draw_arrow(draw, arrow_x, arrow_y, direction, arrow_col)

        return img
