#!/usr/bin/env python3

import time
from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw

options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.brightness = 80

matrix = RGBMatrix(options=options)

image = Image.new("RGB", (64, 32))
draw = ImageDraw.Draw(image)

draw.rectangle((0, 0, 63, 31), outline=(0, 255, 0))
draw.text((2, 10), "HELLO", fill=(255, 255, 0))

canvas = matrix.CreateFrameCanvas()
canvas.SetImage(image, 0, 0)
matrix.SwapOnVSync(canvas)

while True:
    time.sleep(1)

