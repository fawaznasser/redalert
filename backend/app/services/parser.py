from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.common import EventType

HASHTAG_PATTERN = re.compile(r"#(\S+)")
MULTISPACE_PATTERN = re.compile(r"\s+")
PUNCTUATION_EDGE_PATTERN = re.compile(r"^[^\w\u0600-\u06FF]+|[^\w\u0600-\u06FF]+$")
ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
URL_PATTERN = re.compile(r"(https?://\S+|t\.me/\S+)", re.IGNORECASE)
LOCATION_SPLIT_PATTERN = re.compile(r"[\n\r،,/]+")

ALEF_TRANSLATION = str.maketrans(
    {
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0622": "\u0627",
        "\u0671": "\u0627",
    }
)

EVENT_TAGS = {
    "\u062f\u0631\u0648\u0646": EventType.drone_movement,
    "\u0645\u0633\u064a\u0631": EventType.drone_movement,
    "\u0645\u0633\u064a\u0631\u0629": EventType.drone_movement,
    "\u0645\u0633\u064a\u0631\u0627\u062a": EventType.drone_movement,
    "\u0637\u0627\u0626\u0631\u0629 \u0645\u0633\u064a\u0631\u0629": EventType.drone_movement,
    "\u0645\u0642\u0627\u062a\u0644\u0627\u062a \u062d\u0631\u0628\u064a\u0629": EventType.fighter_jet_movement,
    "\u0645\u0631\u0648\u062d\u064a": EventType.helicopter_movement,
    "\u0645\u0631\u0648\u062d\u064a\u0629": EventType.helicopter_movement,
}

EVENT_TEXT_KEYWORDS = [
    ("\u0637\u0627\u0626\u0631\u0629 \u0645\u0633\u064a\u0631\u0629", EventType.drone_movement),
    ("\u0645\u0633\u064a\u0631\u0627\u062a", EventType.drone_movement),
    ("\u0645\u0633\u064a\u0631\u0629", EventType.drone_movement),
    ("\u0645\u0633\u064a\u0631", EventType.drone_movement),
    ("\u062f\u0631\u0648\u0646", EventType.drone_movement),
    ("\u0645\u0642\u0627\u062a\u0644\u0627\u062a \u062d\u0631\u0628\u064a\u0629", EventType.fighter_jet_movement),
    ("\u0645\u0631\u0648\u062d\u064a\u0629", EventType.helicopter_movement),
    ("\u0645\u0631\u0648\u062d\u064a", EventType.helicopter_movement),
]

NON_LOCATION_TAGS = {
    "\u0639\u0627\u062c\u0644",
    "\u0639\u0627\u062c\u0644 \u062c\u062f\u0627",
    "\u0639\u0627\u062c\u0644\u062c\u062f\u0627",
    "\u0647\u0627\u0645",
    "\u0647\u0627\u0645 \u062c\u062f\u0627",
    "\u062d\u0635\u0631\u064a",
    "\u062e\u0628\u0631 \u0639\u0627\u062c\u0644",
    "\u0627\u0646\u062a\u0628\u0627\u0647",
    "\u062a\u062d\u0630\u064a\u0631",
    "\u062a\u062d\u0644\u064a\u0642",
    "\u062d\u064a\u0637\u0629",
    "\u062d\u0630\u0631",
    "\u062d\u064a\u0637\u0629 \u0648\u062d\u0630\u0631",
    "\u0627\u0646\u0630\u0627\u0631",
    "\u0625\u0646\u0630\u0627\u0631",
    "\u062a\u062d\u0630\u064a\u0631 \u0639\u0627\u062c\u0644",
    "\u0645\u0633\u062a\u0645\u0631",
    "\u0648\u0627\u0644\u062c\u0648\u0627\u0631",
    "\u0648 \u0627\u0644\u062c\u0648\u0627\u0631",
    "\u0627\u062a\u062c\u0627\u0647",
    "\u0627\u062a\u062c\u0627\u0647 \u0644\u0628\u0646\u0627\u0646",
    "\u0641\u0648\u0642 \u0627\u0644\u0645\u0646\u0627\u0637\u0642 \u0627\u0644\u062a\u0627\u0644\u064a\u0629",
    "\u0627\u0644\u0645\u0646\u0627\u0637\u0642 \u0627\u0644\u062a\u0627\u0644\u064a\u0629",
    "\u064a\u0631\u062c\u0649 \u0627\u0644\u062d\u0630\u0631",
    "\u0631\u062c\u0627\u0621 \u0627\u0644\u062d\u0630\u0631",
    "\u062c\u0646\u0648\u0628 \u0644\u0628\u0646\u0627\u0646",
    "\u062a\u062d\u062f\u064a\u062b",
}

NON_LOCATION_SUBSTRINGS = (
    "\u062d\u064a\u0637\u0629 \u0648\u062d\u0630\u0631",
    "\u062e\u0628\u0631 \u0639\u0627\u062c\u0644",
    "\u0648\u0627\u0644\u062c\u0648\u0627\u0631",
    "\u0627\u0644\u0645\u0646\u0627\u0637\u0642 \u0627\u0644\u062a\u0627\u0644\u064a\u0629",
)

NON_LOCATION_PREFIXES = (
    "\u0627\u062a\u062c\u0627\u0647 ",
    "\u0641\u0648\u0642 ",
)


@dataclass(slots=True)
class ParsedTelegramMessage:
    event_type: EventType | None
    event_tag: str | None
    hashtags: list[str]
    candidate_locations: list[str]
    is_continuation: bool


def detect_event_from_tag(tag: str) -> tuple[EventType | None, str | None]:
    normalized_tag = normalize_hashtag(tag)
    if not normalized_tag:
        return None, None

    if normalized_tag in EVENT_TAGS:
        return EVENT_TAGS[normalized_tag], normalized_tag

    for keyword, event_type in EVENT_TEXT_KEYWORDS:
        if keyword in normalized_tag:
            return event_type, keyword

    return None, None


def normalize_hashtag(tag: str) -> str:
    normalized = PUNCTUATION_EDGE_PATTERN.sub("", tag)
    normalized = normalized.replace("_", " ")
    normalized = normalized.translate(ALEF_TRANSLATION)
    normalized = normalized.replace("\u0640", "")
    normalized = ARABIC_DIACRITICS_PATTERN.sub("", normalized)
    normalized = MULTISPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = text.replace("_", " ")
    normalized = PUNCTUATION_EDGE_PATTERN.sub("", normalized)
    normalized = normalized.translate(ALEF_TRANSLATION)
    normalized = normalized.replace("\u0640", "")
    normalized = ARABIC_DIACRITICS_PATTERN.sub("", normalized)
    normalized = MULTISPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def is_non_location_text(text: str) -> bool:
    if not text:
        return True
    if text in NON_LOCATION_TAGS:
        return True
    if any(text.startswith(prefix) for prefix in NON_LOCATION_PREFIXES):
        return True
    return any(fragment in text for fragment in NON_LOCATION_SUBSTRINGS)


def is_location_candidate(tag: str) -> bool:
    normalized = normalize_hashtag(tag)
    if not normalized:
        return False
    event_type, _ = detect_event_from_tag(normalized)
    if event_type is not None:
        return False
    if is_non_location_text(normalized):
        return False
    return True


def extract_hashtags(message_text: str | None) -> list[str]:
    if not message_text:
        return []
    return [normalize_hashtag(match.group(1)) for match in HASHTAG_PATTERN.finditer(message_text)]


def extract_text_location_candidates(message_text: str | None) -> list[str]:
    if not message_text:
        return []

    # Remove hashtags and links first so plain-text village lines can be read deterministically.
    text_without_hashtags = HASHTAG_PATTERN.sub(" ", message_text)
    text_without_links = URL_PATTERN.sub(" ", text_without_hashtags)
    candidates: list[str] = []

    for part in LOCATION_SPLIT_PATTERN.split(text_without_links):
        normalized = normalize_text(part)
        if not normalized:
            continue
        if is_non_location_text(normalized):
            continue
        if detect_event_from_tag(normalized)[0] is not None:
            continue
        if detect_event_from_text(normalized)[0] is not None:
            continue
        # Keep short Arabic place-like lines only; avoid turning whole sentences into locations.
        if len(normalized.split()) > 4:
            continue
        if not re.search(r"[\u0600-\u06FF]", normalized):
            continue
        candidates.append(normalized)

    return candidates


def detect_event_from_text(message_text: str | None) -> tuple[EventType | None, str | None]:
    normalized_text = normalize_text(message_text)
    if not normalized_text:
        return None, None

    for keyword, event_type in EVENT_TEXT_KEYWORDS:
        if keyword in normalized_text:
            return event_type, keyword
    return None, None


def detect_continuation(message_text: str | None, hashtags: list[str]) -> bool:
    normalized_text = normalize_text(message_text)
    if "\u0645\u0633\u062a\u0645\u0631" in normalized_text:
        return True
    return any(normalize_hashtag(tag) == "\u0645\u0633\u062a\u0645\u0631" for tag in hashtags)


def parse_message_text(message_text: str | None) -> ParsedTelegramMessage | None:
    hashtags = extract_hashtags(message_text)
    is_continuation = detect_continuation(message_text, hashtags)

    event_type: EventType | None = None
    event_tag: str | None = None
    candidate_locations: list[str] = []

    for tag in hashtags:
        if event_type is None:
            matched_type, matched_tag = detect_event_from_tag(tag)
            if matched_type is not None and matched_tag is not None:
                event_type = matched_type
                event_tag = matched_tag
                continue
        if is_location_candidate(tag):
            candidate_locations.append(tag)

    for candidate in extract_text_location_candidates(message_text):
        if candidate not in candidate_locations:
            candidate_locations.append(candidate)

    if event_type is None:
        event_type, event_tag = detect_event_from_text(message_text)

    if event_type is None and not is_continuation:
        return None

    if event_type is None and is_continuation:
        event_type = EventType.drone_movement
        event_tag = "\u0645\u0633\u062a\u0645\u0631"

    if event_tag is None:
        return None

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidate_locations:
        if candidate not in seen:
            unique_candidates.append(candidate)
            seen.add(candidate)

    return ParsedTelegramMessage(
        event_type=event_type,
        event_tag=event_tag,
        hashtags=hashtags,
        candidate_locations=unique_candidates,
        is_continuation=is_continuation,
    )
