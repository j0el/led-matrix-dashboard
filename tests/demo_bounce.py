#!/usr/bin/env python3

import time
from PIL import Image, ImageDraw

from matrix_config import create_matrix, total_width, total_height


def main():
    matrix = create_matrix()
    width = total_width()
    height = total_height()

    canvas = matrix.CreateFrameCanvas()

    x = 20
    y = 20
    dx = 3
    dy = 2
    r = 8

    while True:
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rectangle((0, 0, width - 1, height - 1), outline=(50, 50, 50))

        draw.line((64, 0, 64, height - 1), fill=(30, 30, 30))
        draw.line((128, 0, 128, height - 1), fill=(30, 30, 30))

        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 50, 50))

        canvas.SetImage(image, 0, 0)
        canvas = matrix.SwapOnVSync(canvas)

        x += dx
        y += dy

        if x - r <= 0 or x + r >= width - 1:
            dx *= -1
        if y - r <= 0 or y + r >= height - 1:
            dy *= -1

        time.sleep(0.02)


if __name__ == "__main__":
    main()

