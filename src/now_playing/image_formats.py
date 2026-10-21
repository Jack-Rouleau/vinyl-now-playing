"""Validate cached image format and decoded dimensions without ML dependencies."""

MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    position = 2
    while position + 4 <= len(data):
        if data[position] != 255:
            break
        while position < len(data) and data[position] == 255:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0xD9, 0xDA) or position + 2 > len(data):
            break
        length = int.from_bytes(data[position : position + 2], "big")
        if length < 2 or position + length > len(data):
            break
        if (
            marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF)
            and length >= 8
        ):
            return int.from_bytes(data[position + 5 : position + 7], "big"), int.from_bytes(
                data[position + 3 : position + 5], "big"
            )
        position += length
    raise ValueError("Invalid JPEG dimensions")


def image_suffix(data: bytes) -> str:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Artwork exceeds 8 MiB")
    if len(data) > 32 and data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        suffix = ".jpg"
        width, height = _jpeg_dimensions(data)
    elif (
        len(data) > 32
        and data.startswith(b"\x89PNG\r\n\x1a\n")
        and data[12:16] == b"IHDR"
        and b"IEND" in data[-12:]
    ):
        suffix = ".png"
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    elif (
        len(data) > 32
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
        and int.from_bytes(data[4:8], "little") + 8 == len(data)
    ):
        suffix = ".webp"
        if data[12:16] == b"VP8X":
            width, height = (
                1 + int.from_bytes(data[24:27], "little"),
                1 + int.from_bytes(data[27:30], "little"),
            )
        elif data[12:16] == b"VP8L" and data[20] == 0x2F:
            packed = int.from_bytes(data[21:25], "little")
            width, height = 1 + (packed & 0x3FFF), 1 + ((packed >> 14) & 0x3FFF)
        elif data[12:16] == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            width, height = (
                int.from_bytes(data[26:28], "little") & 0x3FFF,
                int.from_bytes(data[28:30], "little") & 0x3FFF,
            )
        else:
            raise ValueError("Invalid WebP dimensions")
    else:
        raise ValueError("Artwork is not a supported complete image")
    if not (0 < width <= 4096 and 0 < height <= 4096) or width * height > 4_000_000:
        raise ValueError("Artwork dimensions exceed the 4-megapixel cache limit")
    return suffix
