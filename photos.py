"""
Preparing photos before they're sent to Claude.

iPad photos are large (often 3-5 MB). We shrink each one so it uploads
quickly and costs less, while the labels stay easy to read.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

# Longest side, in pixels, after shrinking. Labels are still sharp at this size.
MAX_SIDE = 1568

# How many photos can be sent at once.
MAX_PHOTOS = 5


class PhotoError(Exception):
    """A photo couldn't be used, with a message that's safe to show on screen."""


def prepare_photo(photo_bytes, filename="photo"):
    """
    Turn an uploaded photo into a smaller JPEG.
    Raises PhotoError if the file isn't a photo we can read.
    """
    try:
        image = Image.open(io.BytesIO(photo_bytes))
        image = ImageOps.exif_transpose(image)  # keep the photo the right way up
    except (UnidentifiedImageError, OSError):
        raise PhotoError(f"Couldn't read {filename}. Please use a JPEG or PNG photo.")

    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()
