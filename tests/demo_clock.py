#!/usr/bin/env python3

import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from matrix_config import create_matrix, total_width, total_height


def main():
    matrix = create_matrix()
    width = total_width()
    height = total_height()

    canvas = matrix.CreateFrameCanvas()

    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Menlo.ttc", 28)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    while True:
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p").lstrip("0")
        date_str = now.strftime("%A, %B %d, %Y")

        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rectangle((0, 0, width - 1, height - 1), outline=(20, 80, 20))

        bbox_time = draw.textbbox((0, 0), time_str, font=font_big)
        time_w = bbox_time[2] - bbox_time[0]
        time_h = bbox_time[3] - bbox_time[1]

        bbox_date = draw.textbbox((0, 0), date_str, font=font_small)
        date_w = bbox_date[2] - bbox_date[0]

        time_x = (width - time_w) // 2
        time_y = 12
        date_x = (width - date_w) // 2
        date_y = time_y + time_h + 8

        draw.text((time_x, time_y), time_str, font=font_big, fill=(80, 220, 255))
        draw.text((date_x, date_y), date_str, font=font_small, fill=(255, 180, 60))

        canvas.SetImage(image, 0, 0)
        canvas = matrix.SwapOnVSync(canvas)

        time.sleep(0.1)


if __name__ == "__main__":
    main()

