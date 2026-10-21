import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from now_playing.model_setup import ensure_model, install_archive, model_is_ready

FILES = {
    "saved_model.pb": b"model",
    "variables/variables.index": b"index",
    "variables/variables.data-00000-of-00001": b"data",
    "assets/yamnet_class_map.csv": b"index,mid,display_name\n0,id,Speech\n",
}


def archive_at(path, files=FILES, link=None):
    with tarfile.open(path, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        if link:
            info = tarfile.TarInfo(link)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            archive.addfile(info)


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="now playing ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "models/yamnet"
        self.archive = self.root / "model.tar.gz"

    def test_installs_valid_model_and_reuses_without_download(self):
        archive_at(self.archive)
        install_archive(self.archive, self.target)
        self.assertTrue(model_is_ready(self.target))

        def unexpected(*_):
            self.fail("valid model should not be downloaded again")

        self.assertEqual(ensure_model(self.target, downloader=unexpected), self.target.absolute())

    def test_rejects_unsafe_members_without_damaging_existing_files(self):
        self.target.mkdir(parents=True)
        marker = self.target / "keep.txt"
        marker.write_text("original")
        for name in ("../escape", "/absolute", "C:/windows/file", "assets\\escape", "extra.exe"):
            with self.subTest(name=name):
                archive_at(self.archive, {**FILES, name: b"bad"})
                with self.assertRaises(ValueError):
                    install_archive(self.archive, self.target)
                self.assertEqual(marker.read_text(), "original")
        archive_at(self.archive, link="assets/link")
        with self.assertRaises(ValueError):
            install_archive(self.archive, self.target)
        self.assertFalse((self.root / "escape").exists())

    def test_incomplete_archive_does_not_replace_old_model(self):
        self.target.mkdir(parents=True)
        (self.target / "keep.txt").write_text("original")
        archive_at(self.archive, {"saved_model.pb": b"partial"})
        with self.assertRaisesRegex(ValueError, "incomplete"):
            install_archive(self.archive, self.target)
        self.assertEqual((self.target / "keep.txt").read_text(), "original")
