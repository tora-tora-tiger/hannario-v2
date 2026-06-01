import unittest

from scripts.operator_quality_review import ReviewItem
from scripts.operator_recommendations import recommendation_lines, top_examples


class OperatorRecommendationsTest(unittest.TestCase):
    def test_recommendation_lines_for_common_review_items(self):
        items = [
            ReviewItem(
                severity="high",
                category="fallback",
                timestamp="t1",
                channel="#general",
                author="user",
                reason="fallback",
            ),
            ReviewItem(
                severity="medium",
                category="long_reply",
                timestamp="t2",
                channel="#general",
                author="user",
                reason="long",
            ),
            ReviewItem(
                severity="low",
                category="trigger_random",
                timestamp="t3",
                channel="#general",
                author="user",
                reason="random",
            ),
        ]

        lines = recommendation_lines(items)
        text = "\n".join(lines)

        self.assertIn("fallback", text)
        self.assertIn("smoke_letta.py", text)
        self.assertIn("long reply", text)
        self.assertIn("random participation", text)

    def test_recommendation_lines_has_no_change_case(self):
        lines = recommendation_lines([])

        self.assertEqual(
            lines,
            ["- No immediate configuration changes recommended from the selected logs."],
        )

    def test_top_examples(self):
        items = [
            ReviewItem(
                severity="high",
                category="fallback",
                timestamp="t1",
                channel="#general",
                author="user",
                reason="fallback happened",
            )
        ]

        self.assertEqual(
            top_examples(items),
            ["- [high] fallback at t1 #general: fallback happened"],
        )


if __name__ == "__main__":
    unittest.main()
