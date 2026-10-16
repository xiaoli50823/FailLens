import tempfile
import unittest
from pathlib import Path

from faillens.analyzer import analyze
from faillens.junit import load_results


class JunitAndHistoryTests(unittest.TestCase):
    def test_example_runs_are_parsed_and_flaky_is_detected(self):
        results, runs = load_results(["examples/runs"])
        report = analyze(results, runs, ["examples/runs"], "demo")
        self.assertEqual(8, len(results))
        flaky = {item.test_id for item in report.histories if item.is_flaky}
        self.assertIn("tests.ui.TestCheckout::test_submit_order", flaky)
        self.assertIn("tests.api.TestUser::test_register_user", flaky)
        checkout = next(item for item in results if item.test_id.endswith("test_submit_order") and item.status == "failed")
        self.assertIn("legacy selector", checkout.artifact_text)

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            load_results(["does-not-exist"])

    def test_empty_suite_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "junit.xml"
            path.write_text("<testsuite></testsuite>", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_results([str(path)])


if __name__ == "__main__":
    unittest.main()

