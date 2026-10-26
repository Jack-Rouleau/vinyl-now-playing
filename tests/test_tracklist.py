import unittest

from now_playing.models import Track


def row(n, **extra):
    return dict(
        kind="song",
        trackId=n,
        collectionId=42,
        trackName=f"Song {n}",
        artistName="Artist",
        collectionName="Album",
        trackTimeMillis=100000,
        discNumber=1,
        discCount=1,
        trackNumber=n,
        trackCount=2,
        **extra,
    )


class TracklistTests(unittest.IsolatedAsyncioTestCase):
    async def test_ordered_tracks_durations_and_cache(self):
        from now_playing.tracklist import TracklistProvider

        calls = []

        async def fetch(path, params):
            calls.append(path)
            return {"results": [row(1)] if path == "search" else [row(2), row(1)]}

        provider = TracklistProvider(fetcher=fetch)
        track = Track("shazam", "Song 1", "Artist", "Album")
        tracks = await provider.resolve(track)
        self.assertEqual([t.track.title for t in tracks], ["Song 1", "Song 2"])
        self.assertEqual([t.duration for t in tracks], [100, 100])
        self.assertEqual(await provider.resolve(Track("2", "Song 2", "Artist", "Album")), tracks)
        self.assertEqual(calls, ["search", "lookup"])

    async def test_mismatched_and_incomplete_metadata_are_rejected(self):
        from now_playing.tracklist import TracklistProvider

        track = Track("1", "Song 1", "Artist", "Album")
        for rows in (
            [row(1)],
            [row(1), row(1)],
            [row(1), {**row(2), "trackTimeMillis": 0}],
            [row(1), {**row(2), "trackNumber": 3}],
            [{**row(1), "discCount": 2}, {**row(2), "discCount": 2}],
            [row(1), {**row(2), "trackId": 1}],
            [row(1), {**row(2), "collectionId": 99}],
            [row(1), {**row(2), "trackTimeMillis": float("nan")}],
            [row(1), {**row(2), "collectionName": "Different"}],
        ):

            async def fetch(path, params):
                return {"results": [row(1)] if path == "search" else rows}

            with self.subTest(rows=rows):
                self.assertEqual(await TracklistProvider(fetcher=fetch).resolve(track), ())

    async def test_wrong_artist_or_edition_does_not_guess(self):
        from now_playing.tracklist import TracklistProvider

        for replacement in (
            {"artistName": "Other"},
            {"collectionName": "Album (Live)"},
            {"trackName": "Song 1 (Live)"},
        ):

            async def fetch(path, params):
                return {"results": [{**row(1), **replacement}]}

            self.assertEqual(
                await TracklistProvider(fetcher=fetch).resolve(
                    Track("1", "Song 1", "Artist", "Album")
                ),
                (),
            )

    async def test_lookup_failures_are_negative_cached(self):
        from now_playing.tracklist import TracklistProvider

        calls = []

        async def fetch(path, params):
            calls.append(path)
            raise OSError("offline")

        provider = TracklistProvider(fetcher=fetch)
        track = Track("1", "Song 1", "Artist", "Album")
        self.assertEqual(await provider.resolve(track), ())
        self.assertEqual(await provider.resolve(track), ())
        self.assertEqual(len(calls), 1)
