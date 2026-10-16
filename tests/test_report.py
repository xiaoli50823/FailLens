import tempfile
import unittest
from pathlib import Path

from faillens.analyzer import analyze
from faillens.junit import load_results
from faillens.report import write_reports


class ReportTests(unittest.TestCase):
    def test_html_json_and_artifacts_are_written(self):
        results, runs = load_results(["examples/runs"])
        report = analyze(results, runs, ["examples/runs"], "商城诊断")
        with tempfile.TemporaryDirectory() as directory:
            html_path, json_path = write_reports(report, Path(directory))
            page = html_path.read_text(encoding="utf-8")
            payload = json_path.read_text(encoding="utf-8")
            self.assertIn("商城诊断", page)
            self.assertIn("元素定位失败", page)
            self.assertNotIn("raw.includes('{\"project\"", page)
            self.assertIn('"flaky_score"', payload)
            self.assertTrue((Path(directory) / "artifacts" / "case-1" / "1-browser.log").exists())


if __name__ == "__main__":
    unittest.main()
