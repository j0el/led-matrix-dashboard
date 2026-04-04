#!/usr/bin/env python3

import sys
import time
from PIL import Image

from matrix_config import create_matrix, total_width, total_height


def main():
    if len(sys.argv) < 2:
        print("Usage: python demo_image.py path/to/image.png")
        sys.exit(1)

    image_path = sys.argv[1]

    matrix = create_matrix()
    width = total_width()
    height = total_height()

    canvas = matrix.CreateFrameCanvas()

    image = Image.open(image_path).convert("RGB")
    image = image.resize((width, height))

    while True:
        canvas.SetImage(image, 0, 0)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(1)


if __name__ == "__main__":
    main(
)
