from matrix_compat import RGBMatrix, RGBMatrixOptions

DISPLAY_ROWS = 64
DISPLAY_COLS = 64
DISPLAY_CHAIN_LENGTH = 3
DISPLAY_PARALLEL = 1
DISPLAY_BRIGHTNESS = 80


def create_matrix():
    options = RGBMatrixOptions()
    options.rows = DISPLAY_ROWS
    options.cols = DISPLAY_COLS
    options.chain_length = DISPLAY_CHAIN_LENGTH
    options.parallel = DISPLAY_PARALLEL
    options.brightness = DISPLAY_BRIGHTNESS
    return RGBMatrix(options=options)


def total_width():
    return DISPLAY_COLS * DISPLAY_CHAIN_LENGTH


def total_height():
    return DISPLAY_ROWS

