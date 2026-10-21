import base64
import tempfile
import unittest
from pathlib import Path

from now_playing.album_cache import MAX_IMAGE_BYTES, AlbumArchive, image_suffix
from now_playing.albums import AlbumStore
from now_playing.models import Track

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN1kAAAAASUVORK5CYII="
)


class ImageTests(unittest.TestCase):
    def test_rejects_html_truncated_and_oversized_images(self):
        self.assertEqual(image_suffix(PNG), ".png")
        for data in (
            b"<html>Not artwork</html>",
            b"\xff\xd8truncated",
            b"x" * (MAX_IMAGE_BYTES + 1),
        ):
            with self.assertRaises(ValueError):
                image_suffix(data)

    def test_rejects_compressed_images_with_excessive_dimensions(self):
        import struct
        import zlib

        def chunk(kind, data):
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data))
            )

        ihdr = struct.pack(">IIBBBBB", 20000, 20000, 8, 0, 0, 0, 0)
        compressor = zlib.compressobj()
        compressed = (
            b"".join(compressor.compress(b"\0" * 20001) for _ in range(20000)) + compressor.flush()
        )
        data = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", compressed)
            + chunk(b"IEND", b"")
        )
        self.assertLess(len(data), MAX_IMAGE_BYTES)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            image_suffix(data)


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_high_resolution_fallback_and_local_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlbumStore(Path(directory))
            requests = []

            async def fetch(url):
                requests.append(url)
                if "1200x1200" in url:
                    raise OSError("not available")
                return PNG

            archive = AlbumArchive(store, fetcher=fetch)
            track = Track(
                "1",
                "Song",
                "Artist",
                "Album",
                "https://is1-ssl.mzstatic.com/image/thumb/a.jpg/400x400cc.jpg",
            )
            await archive.record(track)
            await archive.cache_album(store.pending()[0])
            self.assertEqual(len(requests), 2)
            self.assertIn("1200x1200", requests[0])
            key = store.snapshot()["albums"][0]["id"]
            self.assertEqual(store.artwork(key), ("image/png", PNG))
            self.assertEqual(store.pending(), [])
            await archive.close()

    async def test_failed_cache_retains_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AlbumStore(Path(directory))

            async def fetch(_):
                return b"<html>wrong</html>"

            archive = AlbumArchive(store, fetcher=fetch)
            await archive.record(Track("1", "Song", "Artist", "Album", "https://example.com/image"))
            with self.assertLogs("now_playing.album_cache", level="WARNING"):
                await archive.cache_album(store.pending()[0])
            self.assertEqual(len(store.pending()), 1)
            self.assertEqual(store.snapshot()["albums"], [])
            self.assertEqual(list(store.cache.iterdir()), [])
            await archive.close()

    async def test_storage_failure_does_not_escape_to_recognition(self):
        class Store:
            def record(self, _):
                raise OSError("disk unavailable")

        archive = AlbumArchive(Store())
        with self.assertLogs("now_playing.album_cache", level="ERROR"):
            self.assertIsNone(await archive.record(Track("1", "Song", "Artist", "Album")))
        await archive.close()

    async def test_oversized_download_is_stopped(self):
        from now_playing.album_cache import download_image

        class Content:
            async def iter_chunked(self, _):
                yield b"x" * MAX_IMAGE_BYTES
                yield b"overflow"

        class Response:
            content_length = None
            content = Content()

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        class Session:
            def get(self, _):
                return Response()

        with self.assertRaisesRegex(ValueError, "8 MiB"):
            await download_image(Session(), "https://example.com/art.jpg")
