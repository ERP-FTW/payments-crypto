from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.check_odoo_scaffolds import EXPECTED, validate_repository


ROOT = Path(__file__).resolve().parents[1]


class ScaffoldTestCase(unittest.TestCase):
    def test_repository_satisfies_phase_one_contract(self):
        self.assertEqual(validate_repository(ROOT), [])

    def test_every_scaffold_is_an_importable_python_package(self):
        for module in EXPECTED:
            package = ROOT / "addons" / module / "__init__.py"
            spec = importlib.util.spec_from_file_location(module, package)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            loaded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loaded)

    def test_validator_reports_a_missing_manifest_data_file(self):
        with self._repository_copy() as copied:
            manifest = copied / "addons" / "crypto_base" / "__manifest__.py"
            text = manifest.read_text()
            manifest.write_text(
                text.replace(
                    "'views/crypto_base_menus.xml'",
                    "'views/does_not_exist.xml'",
                )
            )
            self.assertIn(
                "crypto_base: missing data file views/does_not_exist.xml",
                validate_repository(copied),
            )

    def test_validator_reports_forbidden_provider_dependency(self):
        with self._repository_copy() as copied:
            manifest = copied / "addons" / "crypto_provider_btcpay" / "__manifest__.py"
            manifest.write_text(
                manifest.read_text().replace(
                    "'depends': ['crypto_base']",
                    "'depends': ['crypto_base', 'payment']",
                )
            )
            failures = validate_repository(copied)
            self.assertIn(
                "crypto_provider_btcpay: forbidden provider dependencies: payment",
                failures,
            )

    def _repository_copy(self):
        temporary = tempfile.TemporaryDirectory()
        copied = Path(temporary.name)
        shutil.copytree(ROOT / "addons", copied / "addons")

        class RepositoryCopy:
            def __enter__(self):
                return copied

            def __exit__(self, *_args):
                temporary.cleanup()

        return RepositoryCopy()


if __name__ == "__main__":
    unittest.main()
