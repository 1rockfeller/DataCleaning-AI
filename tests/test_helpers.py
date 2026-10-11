import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# load_dotenv() does not override variables that are already set.
os.environ.update(
    AZURE_OPENAI_KEY="test-key",
    URL="https://example.openai.azure.com",
    API_VERSION="2024-05-01-preview",
    AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="test-deployment",
)

import final  # noqa: E402


class LoadCsvFileTests(unittest.TestCase):
    def test_flattens_rows_into_one_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.csv"
            path.write_text("a,b\n1,x\n2,y\n", encoding="utf-8")
            self.assertEqual(final.load_csv_file(str(path)), "1, x, 2, y")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            final.load_csv_file("does-not-exist.csv")


class LoadLogsTests(unittest.TestCase):
    LOG_NAME = "test_load_logs.log"

    def tearDown(self):
        (ROOT / "logs" / self.LOG_NAME).unlink(missing_ok=True)

    def test_strips_lines_and_skips_blanks(self):
        (ROOT / "logs" / self.LOG_NAME).write_text("  first  \n\n second\n", encoding="utf-8")
        self.assertEqual(final.load_logs(self.LOG_NAME), ["first", "second"])

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(final.load_logs("no-such-file.log"), [])


class PythonExecutorTests(unittest.TestCase):
    def setUp(self):
        self.executor = final.PythonExecutor()

    def test_valid_code_succeeds(self):
        self.assertEqual(self.executor.run("value = 1 + 1"), (True, None))

    def test_exception_returns_traceback(self):
        succeeded, error = self.executor.run("1 / 0")
        self.assertFalse(succeeded)
        self.assertIn("ZeroDivisionError", error)

    def test_syntax_error_is_reported(self):
        succeeded, error = self.executor.run("def broken(:")
        self.assertFalse(succeeded)
        self.assertIn("SyntaxError", error)

    def test_empty_code_is_rejected(self):
        succeeded, error = self.executor.run("   ")
        self.assertFalse(succeeded)
        self.assertTrue(error)


class ApprovalTests(unittest.TestCase):
    def test_detects_approval_forms(self):
        for text in ("Approved", "**Approved**", "approved - all checks pass", '{"title": "Approved"}'):
            self.assertTrue(final.is_approval(text), text)

    def test_ignores_incidental_mentions(self):
        for text in ("# Report\nThe step was approved by a human.", '{"title": "Failed"}', "Not approved", "", None):
            self.assertFalse(final.is_approval(text), text)

    def test_only_checkers_can_end_chats(self):
        analysis = final.analysis_chat.termination_strategy
        report = final.report_chat.termination_strategy
        self.assertEqual([a.name for a in analysis.agents], ["AnalysisChecker"])
        self.assertEqual([a.name for a in report.agents], ["ReportChecker"])


class SaveFinalReportTests(unittest.TestCase):
    def test_creates_directory_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "report.md"
            final.save_final_report("# Report", str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), "# Report")


if __name__ == "__main__":
    unittest.main()
