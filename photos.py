"""
Preparing photos and PDFs before they're sent to Claude.

iPad photos are large (often 3-5 MB). We shrink each one so it uploads
quickly and costs less, while the labels stay easy to read.
PDFs (for example receipts from emails) are sent as they are.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

# Longest side, in pixels, after shrinking. Labels are still sharp at this size.
MAX_SIDE = 1568

# How many photos or PDFs can be sent at once.
MAX_PHOTOS = 5

# The biggest PDF we accept. Receipts are usually well under 1 MB.
MAX_PDF_BYTES = 10 * 1024 * 1024


class PhotoError(Exception):
    """A file couldn't be used, with a message that's safe to show on screen."""


def is_pdf(file_bytes):
    """Every PDF file starts with the characters %PDF."""
    return file_bytes[:5] == b"%PDF-"


def prepare_upload(file_bytes, filename="file"):
    """
    Get an uploaded file ready for Claude. Returns a dictionary:
      {"media_type": "application/pdf" or "image/jpeg", "data": the file's bytes}
    Raises PhotoError if the file can't be used.
    """
    if is_pdf(file_bytes):
        if len(file_bytes) > MAX_PDF_BYTES:
            raise PhotoError(f"{filename} is too big. PDFs must be under 10 MB.")
        return {"media_type": "application/pdf", "data": file_bytes}
    return {"media_type": "image/jpeg", "data": prepare_photo(file_bytes, filename)}


def prepare_photo(photo_bytes, filename="photo"):
    """
    Turn an uploaded photo into a smaller JPEG.
    Raises PhotoError if the file isn't a photo we can read.
    """
    try:
        image = Image.open(io.BytesIO(photo_bytes))
        image = ImageOps.exif_transpose(image)  # keep the photo the right way up
    except (UnidentifiedImageError, OSError):
        raise PhotoError(f"Couldn't read {filename}. Please use a photo (JPEG or PNG) or a PDF.")

    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()
