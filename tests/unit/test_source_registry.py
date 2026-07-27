from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from source_registry import SourceRegistryConfigError, load_source_registry


class SourceRegistryTests(unittest.TestCase):
    def test_loads_local_registry(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sources.toml"
            path.write_text(
                "registry_version = '0.1'\n"
                "[[sources]]\n"
                "name = 'fixture_source'\n"
                "enabled = false\n"
                "identity_strategy = 'stable_source_key'\n",
                encoding="utf-8",
            )
            registry = load_source_registry(path)
        self.assertEqual(registry.sources[0].name, "fixture_source")
        self.assertFalse(registry.sources[0].enabled)

    def test_rejects_duplicate_source_names(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sources.toml"
            path.write_text(
                "registry_version = '0.1'\n"
                "[[sources]]\nname = 'fixture_source'\nenabled = false\nidentity_strategy = 'stable_source_key'\n"
                "[[sources]]\nname = 'fixture_source'\nenabled = false\nidentity_strategy = 'stable_source_key'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SourceRegistryConfigError, "unique"):
                load_source_registry(path)
