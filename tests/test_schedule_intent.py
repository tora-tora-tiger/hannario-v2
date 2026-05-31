import unittest

from schedule_intent import (
    AmbiguousScheduleIntent,
    RelativeScheduleIntent,
    normalize_digits,
    parse_ambiguous_schedule_intent,
    parse_relative_schedule_intent,
)


class ScheduleIntentTest(unittest.TestCase):
    def test_normalize_digits(self) -> None:
        self.assertEqual(normalize_digits("１０分後"), "10分後")

    def test_parse_relative_schedule_intent_minutes(self) -> None:
        intent = parse_relative_schedule_intent("10分後に「自然言語日時テスト」って言って")

        self.assertEqual(intent, RelativeScheduleIntent(minutes=10, message="自然言語日時テスト"))

    def test_parse_relative_schedule_intent_hours(self) -> None:
        intent = parse_relative_schedule_intent("２時間後に『休憩』って言って")

        self.assertEqual(intent, RelativeScheduleIntent(minutes=120, message="休憩"))

    def test_parse_relative_schedule_intent_rejects_too_large_value(self) -> None:
        self.assertIsNone(parse_relative_schedule_intent("99999分後に「遠すぎ」って言って"))

    def test_parse_ambiguous_schedule_intent(self) -> None:
        intent = parse_ambiguous_schedule_intent("夕方に「曖昧日時テスト」って言って")

        self.assertEqual(
            intent,
            AmbiguousScheduleIntent(word="夕方", message="曖昧日時テスト"),
        )

    def test_parse_ambiguous_schedule_intent_requires_schedule_action(self) -> None:
        self.assertIsNone(parse_ambiguous_schedule_intent("夕方の話をしています"))


if __name__ == "__main__":
    unittest.main()
