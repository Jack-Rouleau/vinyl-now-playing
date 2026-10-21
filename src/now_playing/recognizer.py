"""Replaceable ShazamIO adapter; audio is encoded into memory only."""

import asyncio
import io
import wave

from .artwork import safe_artwork_url
from .models import Track


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_track(payload: dict) -> Track | None:
    track = payload.get("track") if isinstance(payload, dict) else None
    if not isinstance(track, dict):
        return None
    key, title, artist = (_text(track.get(field)) for field in ("key", "title", "subtitle"))
    if not all((key, title, artist)):
        return None
    images = track.get("images")
    artwork = (
        _text(images.get("coverarthq") or images.get("coverart"))
        if isinstance(images, dict)
        else None
    )
    artwork = safe_artwork_url(artwork)
    album = None
    sections = track.get("sections")
    for section in sections if isinstance(sections, list) else []:
        if not isinstance(section, dict):
            continue
        metadata = section.get("metadata")
        for item in metadata if isinstance(metadata, list) else []:
            if isinstance(item, dict) and item.get("title") == "Album":
                album = _text(item.get("text"))
    return Track(key, title, artist, album, artwork)


def wav_bytes(samples, sample_rate: int) -> bytes:
    import numpy as np

    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm.tobytes())
    return output.getvalue()


class Recognizer:
    def __init__(self, provider=None):
        self.provider = provider

    async def __aenter__(self):
        if self.provider is None:
            from shazamio import Shazam

            self.provider = Shazam()
        return self

    async def recognize(self, samples, sample_rate: int) -> Track | None:
        data = await asyncio.to_thread(wav_bytes, samples, sample_rate)
        return parse_track(await self.provider.recognize(data))

    async def __aexit__(self, *args):
        close = getattr(self.provider, "close", None)
        if close:
            await close()
