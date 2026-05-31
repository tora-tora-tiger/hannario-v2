import re
from dataclasses import dataclass


FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
RELATIVE_SCHEDULE_PATTERN = re.compile(
    r"(?P<amount>[0-9０-９]+)\s*(?P<unit>分|時間)後\s*に\s*[「『\"](?P<message>.+?)[」』\"]"
)
AMBIGUOUS_TIME_WORDS = ("夕方", "朝", "夜", "あとで", "そのうち")


@dataclass(frozen=True)
class RelativeScheduleIntent:
    minutes: int
    message: str


@dataclass(frozen=True)
class AmbiguousScheduleIntent:
    word: str
    message: str | None = None


def normalize_digits(text: str) -> str:
    return text.translate(FULLWIDTH_DIGITS)


def parse_relative_schedule_intent(text: str) -> RelativeScheduleIntent | None:
    match = RELATIVE_SCHEDULE_PATTERN.search(normalize_digits(text))
    if match is None:
        return None

    amount = int(match.group("amount"))
    unit = match.group("unit")
    minutes = amount if unit == "分" else amount * 60
    if minutes <= 0 or minutes > 10080:
        return None

    message = " ".join(match.group("message").split())
    if not message:
        return None

    return RelativeScheduleIntent(minutes=minutes, message=message)


def parse_ambiguous_schedule_intent(text: str) -> AmbiguousScheduleIntent | None:
    if not any(phrase in text for phrase in ("言って", "送って", "投稿して", "リマインド")):
        return None

    for word in AMBIGUOUS_TIME_WORDS:
        if word not in text:
            continue
        quoted_message = re.search(r"[「『\"](?P<message>.+?)[」』\"]", text)
        if quoted_message is None:
            return AmbiguousScheduleIntent(word=word)
        return AmbiguousScheduleIntent(
            word=word,
            message=" ".join(quoted_message.group("message").split()),
        )

    return None
