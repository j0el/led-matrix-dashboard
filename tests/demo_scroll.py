#!/usr/bin/env python3

import time
from PIL import Image, ImageDraw, ImageFont

from matrix_config import create_matrix, total_width, total_height


def main():
    matrix = create_matrix()
    width = total_width()
    height = total_height()

    canvas = matrix.CreateFrameCanvas()

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()

    text = " Joel's RGB Matrix Demo Pack  |  192x64 virtual canvas  "
    x = width

    while True:
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rectangle((0, 0, width - 1, height - 1), outline=(0, 60, 120))
        draw.text((x, 18), text, font=font, fill=(255, 220, 40))

        canvas.SetImage(image, 0, 0)
        canvas = matrix.SwapOnVSync(canvas)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]

        x -= 2
        if x < -text_width:
            x = width

        time.sleep(0.03)


if __name__ == "__main__":
    main()

