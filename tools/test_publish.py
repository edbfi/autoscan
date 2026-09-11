# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from publish import validate


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for arch in ("amd64", "arm64"):
            folder = self.root / ("alpinevpn-" + arch)
            folder.mkdir()
            record = {"repository": "edbfi/base-image", "branch": "alpinevpn", "arch": arch,
                      "revision": "a" * 40, "tags": ["alpinevpn"]}
            (folder / "metadata.json").write_text(json.dumps(record))
            for name in ("image.tar", "result.txt", "packages.txt"):
                (folder / name).write_text("fixture")

    def validate(self):
        return validate(self.root, "edbfi/base-image", "alpinevpn")

    def test_complete_pair(self):
        self.assertEqual(self.validate()["revision"], "a" * 40)

    def test_missing_smoke_evidence(self):
        (self.root / "alpinevpn-amd64/result.txt").unlink()
        with self.assertRaises(ValueError): self.validate()

    def test_mixed_revisions(self):
        path = self.root / "alpinevpn-arm64/metadata.json"
        record = json.loads(path.read_text()); record["revision"] = "b" * 40
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError): self.validate()

    def test_other_repository(self):
        path = self.root / "alpinevpn-arm64/metadata.json"
        record = json.loads(path.read_text()); record["repository"] = "other/image"
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError): self.validate()
