from contextlib import redirect_stdout
from io import StringIO
import unittest

from cli.main import main


class CliTests(unittest.TestCase):
    def test_health_is_placeholder_safe(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            status = main(["health"])
        self.assertEqual(status, 0)
        self.assertIn("live acquisition is not implemented", output.getvalue())

    def test_contract_validate_lists_supported_contracts_without_input(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            status = main(["contract", "validate"])
        self.assertEqual(status, 0)
        self.assertIn("DetailFetchJob", output.getvalue())

    def test_source_list_uses_inert_example_registry_by_default(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            status = main(["source", "list"])
        self.assertEqual(status, 0)
        self.assertIn("example_source", output.getvalue())
