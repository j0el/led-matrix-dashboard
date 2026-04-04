#!/usr/bin/env python3

import math
import time
from datetime import datetime

import pandas as pd
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont

from matrix_config import create_matrix, total_width, total_height


TICKERS = [
    ("^DJI", "DOW"),
    ("^GSPC", "S&P"),
    ("^IXIC", "NASDAQ"),
]

PANEL_W = 64
PANEL_H = 64
REFRESH_SECONDS = 60


def load_fonts():
    try:
        title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 10)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 8)
    except Exception:
        title = ImageFont.load_default()
        small = ImageFont.load_default()
    return title, small


def fetch_intraday():
    data = {}
    for ticker, label in TICKERS:
        df = yf.download(
            tickers=ticker,
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if df is None or df.empty:
            data[label] = None
            continue

        # yfinance sometimes returns MultiIndex columns, sometimes not
        if isinstance(df.columns, pd.MultiIndex):
            if ("Close", ticker) in df.columns:
                close = df[("Close", ticker)].dropna()
            else:
                close = df.xs("Close", axis=1, level=0).iloc[:, 0].dropna()
        else:
            close = df["Close"].dropna()

        data[label] = close

    return data


def scale_points(series, x0, y0, w, h):
    values = list(series.values)
    n = len(values)

    if n < 2:
        return []

    vmin = min(values)
    vmax = max(values)

    if math.isclose(vmin, vmax):
        vmax = vmin + 1.0

    points = []
    for i, val in enumerate(values):
        x = x0 + int(i * (w - 1) / max(1, n - 1))
        y = y0 + int((vmax - val) * (h - 1) / (vmax - vmin))
        points.append((x, y))
    return points


def draw_chart(draw, series, panel_x, panel_y, panel_w, panel_h, title, font_title, font_small):
    # outer border
    draw.rectangle(
        (panel_x, panel_y, panel_x + panel_w - 1, panel_y + panel_h - 1),
        outline=(40, 40, 40)
    )

    title_y = panel_y + 2
    chart_x = panel_x + 2
    chart_y = panel_y + 14
    chart_w = panel_w - 4
    chart_h = panel_h - 26

    draw.text((panel_x + 3, title_y), title, font=font_title, fill=(255, 255, 255))

    if series is None or len(series) < 2:
        draw.text((panel_x + 4, panel_y + 28), "No data", font=font_small, fill=(180, 80, 80))
        return

    first_val = float(series.iloc[0])
    last_val = float(series.iloc[-1])
    delta = last_val - first_val
    pct = (delta / first_val * 100.0) if first_val else 0.0

    # baseline grid
    mid_y = chart_y + chart_h // 2
    draw.line((chart_x, mid_y, chart_x + chart_w - 1, mid_y), fill=(25, 25, 25))
    draw.line((chart_x, chart_y, chart_x + chart_w - 1, chart_y), fill=(20, 20, 20))
    draw.line((chart_x, chart_y + chart_h - 1, chart_x + chart_w - 1, chart_y + chart_h - 1), fill=(20, 20, 20))

    points = scale_points(series, chart_x, chart_y, chart_w, chart_h)

    # choose green/red based on day change
    line_color = (60, 220, 90) if delta >= 0 else (220, 70, 70)

    if len(points) >= 2:
        draw.line(points, fill=line_color, width=1)

    value_text = f"{last_val:,.0f}"
    pct_text = f"{pct:+.2f}%"

    draw.text((panel_x + 3, panel_y + panel_h - 10), value_text, font=font_small, fill=(180, 180, 180))

    pct_bbox = draw.textbbox((0, 0), pct_text, font=font_small)
    pct_w = pct_bbox[2] - pct_bbox[0]
    draw.text((panel_x + panel_w - pct_w - 3, panel_y + panel_h - 10), pct_text, font=font_small, fill=line_color)


def render_frame(market_data, font_title, font_small):
    width = total_width()
    height = total_height()

    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    panel_titles = ["DOW", "S&P", "NASDAQ"]

    for i, title in enumerate(panel_titles):
        panel_x = i * PANEL_W
        panel_y = 0
        series = market_data.get(title)
        draw_chart(draw, series, panel_x, panel_y, PANEL_W, PANEL_H, title, font_title, font_small)

    now_str = datetime.now().strftime("%-I:%M %p")
    bbox = draw.textbbox((0, 0), now_str, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.rectangle((width - tw - 6, 0, width - 1, 10), fill=(0, 0, 0))
    draw.text((width - tw - 3, 1), now_str, font=font_small, fill=(120, 120, 120))

    return image


def main():
    matrix = create_matrix()
    canvas = matrix.CreateFrameCanvas()
    font_title, font_small = load_fonts()

    market_data = {label: None for _, label in TICKERS}
    last_refresh = 0

    while True:
        now = time.time()
        if now - last_refresh > REFRESH_SECONDS:
            try:
                market_data = fetch_intraday()
                last_refresh = now
            except Exception as e:
                print(f"Refresh failed: {e}")

        image = render_frame(market_data, font_title, font_small)
        canvas.SetImage(image, 0, 0)
        canvas = matrix.SwapOnVSync(canvas)

        time.sleep(1)


if __name__ == "__main__":
    main()

