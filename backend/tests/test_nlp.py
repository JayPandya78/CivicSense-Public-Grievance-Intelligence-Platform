import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.nlp import analyze_report, detect_language


class NlpAnalysisTests(unittest.TestCase):
    def test_detects_supported_scripts(self):
        self.assertEqual(detect_language("सड़क पर गड्ढा है")[0], "hindi")
        self.assertEqual(detect_language("રસ્તા પર ખાડો છે")[0], "gujarati")
        self.assertEqual(detect_language("There is a pothole")[0], "english")

    def test_suggests_category_and_flags_urgent_language(self):
        result = analyze_report(
            "Emergency: an exposed wire is next to a pothole on the road.",
            "Main Road",
        )
        self.assertEqual(result["suggested_category"], "roads")
        self.assertTrue(result["urgency_flag"])
        self.assertIn("emergency", result["urgency_reasons"])

    def test_flags_spam_without_rejecting_report(self):
        result = analyze_report(
            "Please inspect this civic issue. Buy now at https://example.invalid",
            "Market Street",
        )
        self.assertTrue(result["spam_flag"])
        self.assertTrue(any("buy now" in reason for reason in result["spam_reasons"]))
        self.assertTrue(any("web link" in reason for reason in result["spam_reasons"]))
        self.assertEqual(result["model_type"], "local_rules")

    def test_flags_common_promotional_scam_phrases(self):
        result = analyze_report(
            "Earn money fast with guaranteed returns. Click the link to claim your prize.",
            "Market Street",
        )
        self.assertTrue(result["spam_flag"])
        self.assertTrue(any("earn money" in reason for reason in result["spam_reasons"]))
        self.assertTrue(any("guaranteed returns" in reason for reason in result["spam_reasons"]))

    def test_normal_civic_report_is_not_flagged_as_spam(self):
        result = analyze_report(
            "A water pipe is leaking beside the school and flooding the sidewalk.",
            "Central Road",
        )
        self.assertFalse(result["spam_flag"])
        self.assertEqual(result["spam_reasons"], [])

    def test_flags_obviously_unrelated_text_for_review(self):
        result = analyze_report("This is a test, not a civic issue.", "Central area")
        self.assertTrue(result["spam_flag"])
        self.assertIn("May not describe a civic service issue", result["spam_reasons"])

    def test_flags_short_repeated_character_submissions(self):
        result = analyze_report("nnnnnn", "Anand")
        self.assertTrue(result["spam_flag"])
        self.assertIn("Contains a long repeated character sequence", result["spam_reasons"])

    def test_suggests_public_duplicate_from_text_and_location(self):
        result = analyze_report(
            "A deep pothole is damaging cars on this road.",
            "Main Road",
            existing=[{
                "id": "public-report-id",
                "description": "Deep pothole damaging cars",
                "location": "Main Road",
                "category": "roads",
            }],
        )
        self.assertEqual(result["duplicate_candidates"][0]["id"], "public-report-id")
        self.assertGreaterEqual(result["duplicate_candidates"][0]["similarity"], 0.45)

    def test_summary_is_extractive_and_bounded(self):
        first_sentence = "A blocked drain is flooding the road."
        result = analyze_report(first_sentence + " " + ("Additional details. " * 40), "Central area")
        self.assertEqual(result["summary"], first_sentence)

if __name__ == "__main__":
    unittest.main()
