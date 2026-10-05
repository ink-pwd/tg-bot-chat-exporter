import io

import segno
from aiogram.types import BufferedInputFile


def qr_photo(url: str) -> BufferedInputFile:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=10, border=3)
    return BufferedInputFile(buffer.getvalue(), filename="login.png")
