"""Conservative album matching and bounded iTunes metadata caching."""

import asyncio
import logging
import math
import time
import unicodedata
from collections import OrderedDict

from .models import AlbumTrack, Track

log = logging.getLogger(__name__)


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def same_song(left: Track, right: Track) -> bool:
    return all(
        normalized(getattr(left, key)) == normalized(getattr(right, key))
        for key in ("title", "artist", "album")
    )


def song_index(track, tracks):
    indices = [i for i, entry in enumerate(tracks) if same_song(track, entry.track)]
    return indices[0] if len(indices) == 1 else None


def parse_album(rows, recognized, collection_id):
    songs = [row for row in rows if isinstance(row, dict) and row.get("kind") == "song"]
    if not songs or len(songs) > 200:
        return ()
    ordered = []
    try:
        for row in songs:
            duration = row["trackTimeMillis"]
            disc, number, count = row["discNumber"], row["trackNumber"], row["trackCount"]
            if (
                row["collectionId"] != collection_id
                or normalized(row["collectionName"]) != normalized(recognized.album)
                or not isinstance(row["trackName"], str)
                or not row["trackName"].strip()
                or not isinstance(row["artistName"], str)
                or not row["artistName"].strip()
                or any(type(n) is not int or n < 1 for n in (disc, number, count))
                or type(duration) not in (int, float)
                or not math.isfinite(duration)
                or not 0 < duration <= 7200000
                or count != len(songs)
            ):
                return ()
            track = Track(
                str(row["trackId"]),
                row["trackName"],
                row["artistName"],
                recognized.album,
                recognized.artwork_url,
            )
            ordered.append((disc, number, AlbumTrack(track, duration / 1000)))
        ordered.sort(key=lambda item: item[:2])
        discs = sorted({item[0] for item in ordered})
        if discs != list(range(1, max(discs) + 1)):
            return ()
        if any(
            type(row.get("discCount")) is not int or row["discCount"] != len(discs) for row in songs
        ):
            return ()
        if len({entry.track.id for _, _, entry in ordered}) != len(ordered):
            return ()
        for disc in discs:
            numbers = [number for d, number, _ in ordered if d == disc]
            if numbers != list(range(1, len(numbers) + 1)):
                return ()
        tracks = tuple(item[2] for item in ordered)
        return tracks if song_index(recognized, tracks) is not None else ()
    except (KeyError, TypeError, ValueError):
        return ()


class TracklistProvider:
    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.session = None
        self.cache = OrderedDict()

    async def __aenter__(self):
        import aiohttp

        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8))
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch(self, path, params):
        if self.fetcher:
            return await self.fetcher(path, params)
        async with self.session.get("https://itunes.apple.com/" + path, params=params) as response:
            response.raise_for_status()
            # Apple sometimes serves JSON with a JavaScript content type.
            return await response.json(content_type=None)

    async def resolve(self, track):
        if not track.album:
            return ()
        key = (normalized(track.artist), normalized(track.album))
        cached = self.cache.get(key)
        if cached and time.monotonic() < cached[0]:
            self.cache.move_to_end(key)
            return cached[1] if song_index(track, cached[1]) is not None else ()
        tracks = ()
        try:
            async with asyncio.timeout(12):
                result = await self.fetch(
                    "search",
                    {
                        "term": f"{track.artist} {track.album} {track.title}",
                        "entity": "song",
                        "limit": 50,
                    },
                )
                candidates = [
                    row
                    for row in result.get("results", [])
                    if isinstance(row, dict)
                    and row.get("kind") == "song"
                    and type(row.get("collectionId")) is int
                    and all(
                        normalized(row.get(field)) == normalized(value)
                        for field, value in (
                            ("artistName", track.artist),
                            ("collectionName", track.album),
                            ("trackName", track.title),
                        )
                    )
                ]
                ids = {row["collectionId"] for row in candidates}
                # Prefer no inference to choosing between indistinguishable editions.
                if len(ids) == 1:
                    collection_id = ids.pop()
                    result = await self.fetch(
                        "lookup",
                        {
                            "id": collection_id,
                            "entity": "song",
                            "limit": 200,
                        },
                    )
                    tracks = parse_album(result.get("results", []), track, collection_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.debug("Album track list unavailable; recognition continues", exc_info=True)
        self.cache[key] = (time.monotonic() + (86400 if tracks else 120), tracks)
        self.cache.move_to_end(key)
        while len(self.cache) > 128:
            self.cache.popitem(last=False)
        return tracks
