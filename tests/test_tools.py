import json
import os
import subprocess
import sys
import tarfile
import unittest

from helpers import ROOT, tempdir, write

from export_models import manifest_path


class ExportModelsTests(unittest.TestCase):
    def test_manifest_paths(self):
        self.assertEqual(str(manifest_path("tev1:0.8b")), "registry.ollama.ai/library/tev1/0.8b")
        self.assertEqual(str(manifest_path("qwen2.5")), "registry.ollama.ai/library/qwen2.5/latest")
        self.assertEqual(str(manifest_path("hf.co/org/m:Q4")), "hf.co/org/m/Q4")

    def test_export_tar(self):
        with tempdir() as tmp:
            models = os.path.join(tmp, "models")
            mdir = os.path.join(models, "manifests", "registry.ollama.ai", "library", "tev1")
            os.makedirs(mdir)
            os.makedirs(os.path.join(models, "blobs"))
            manifest = {"config": {"digest": "sha256:aa"}, "layers": [{"digest": "sha256:bb"}]}
            write(os.path.join(mdir, "0.8b"), json.dumps(manifest))
            for h in ("aa", "bb"):
                write(os.path.join(models, "blobs", f"sha256-{h}"), h)
            out = os.path.join(tmp, "out.tar")
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "export_models.py"), "tev1:0.8b",
                                "-d", models, "-o", out], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with tarfile.open(out) as tar:
                names = set(tar.getnames())
            self.assertEqual(names, {"manifests/registry.ollama.ai/library/tev1/0.8b",
                                     "blobs/sha256-aa", "blobs/sha256-bb"})


if __name__ == "__main__":
    unittest.main()
