import unittest

from faillens.diagnosis import diagnose
from faillens.models import RunMetadata, TestResult


def failed(text: str) -> TestResult:
    return TestResult(
        test_id="tests.TestDemo::test_case",
        name="test_case",
        classname="tests.TestDemo",
        status="failed",
        duration=1.0,
        run=RunMetadata(run_id="run", source="junit.xml"),
        message=text,
    )


class DiagnosisTests(unittest.TestCase):
    def test_locator_failure(self):
        result = diagnose(failed('Timeout waiting for locator("#save")'))
        self.assertEqual("locator_failure", result.category)
        self.assertGreater(result.confidence, 0.5)

    def test_application_error_beats_generic_assertion(self):
        result = diagnose(failed("AssertionError: expected 200 got HTTP status 500 Internal Server Error"))
        self.assertEqual("application_error", result.category)

    def test_unknown_failure(self):
        result = diagnose(failed("something unusual happened"))
        self.assertEqual("unknown", result.category)

    def test_passed_has_no_diagnosis(self):
        item = failed("")
        item.status = "passed"
        self.assertIsNone(diagnose(item))


if __name__ == "__main__":
    unittest.main()

