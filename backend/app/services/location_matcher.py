from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.services.parser import normalize_hashtag


@dataclass(slots=True)
class MatchedLocation:
    source_name: str
    location: Location


@dataclass(slots=True)
class LocationMatchResult:
    matches: list[MatchedLocation]
    unmatched: list[str]


@dataclass(slots=True)
class AliasCandidate:
    location: Location
    is_primary: bool


PREFERRED_GOVERNORATE_MARKERS = (
    "south",
    "nabat",
    "\u062c\u0646\u0648\u0628",
    "\u0627\u0644\u062c\u0646\u0648\u0628",
    "\u0627\u0644\u0646\u0628\u0637\u064a\u0629",
)

CHANNEL_LOCATION_ALIASES = {
    "\u0627\u0644\u063a\u0646\u062f\u0648\u0631\u064a\u0629": ("\u063a\u0646\u062f\u0648\u0631\u064a\u0629",),
    "\u0645\u0641\u062f\u0648\u0646": ("\u0645\u064a\u0641\u062f\u0648\u0646",),
    "\u062a\u0648\u0644": ("\u0645\u0632\u0631\u0639\u0629 \u062a\u0648\u0644",),
    "\u0645\u0627\u0631\u0648\u0646 \u0627\u0644\u0631\u0627\u0633": ("\u0645\u0627\u0631\u0648\u0646 \u0627\u0644\u0631\u0623\u0633",),
    "\u0643\u0641\u0631\u0634\u0648\u0628\u0627": ("\u0643\u0641\u0631 \u0634\u0648\u0628\u0627",),
    "\u0643\u0641\u0631\u0643\u0644\u0627": ("\u0643\u0641\u0631 \u0643\u0644\u0627",),
    "\u0643\u0641\u0631\u062a\u0628\u0646\u064a\u062a": ("\u0643\u0641\u0631 \u062a\u0628\u0646\u064a\u062a",),
    "\u064a\u062d\u0631": ("\u064a\u062d\u0645\u0631 \u0627\u0644\u0634\u0642\u064a\u0641",),
    "\u0631\u0628 \u062b\u0644\u0627\u062b\u064a\u0646": ("\u0631\u0628 \u0627\u0644\u062a\u0644\u0627\u062a\u064a\u0646",),
    "\u0639\u064a\u0646\u0627\u062b\u0627": ("\u0639\u064a\u0646\u0627\u062a\u0627",),
    "\u0639\u0631\u0628 \u0635\u0627\u0644\u064a\u0645": ("\u0639\u0631\u0628 \u0635\u0644\u064a\u0645",),
    "\u0639\u0631\u0628\u0635\u0627\u0644\u064a\u0645": ("\u0639\u0631\u0628 \u0635\u0627\u0644\u064a\u0645",),
    "\u0639\u0644\u0645\u0627\u0646 \u0645\u0631\u062c\u0639\u064a\u0648\u0646": ("\u0645\u0631\u062c\u0639\u064a\u0648\u0646",),
    "\u0637\u064a\u0628\u0629": ("\u0627\u0644\u0637\u064a\u0628\u0629",),
    "\u0642\u0644\u0648\u064a\u0647": ("\u0642\u0644\u0648\u064a\u0629",),
    "\u0627\u0644\u0636\u0627\u062d\u064a\u0629": ("\u0627\u0644\u0636\u0627\u062d\u064a\u0629 \u0627\u0644\u062c\u0646\u0648\u0628\u064a\u0629",),
    "\u0627\u0644\u0636\u0627\u062d\u064a\u0629 \u0627\u0644\u062c\u0646\u0648\u0628\u064a\u0629 \u0644\u0628\u064a\u0631\u0648\u062a": ("\u0627\u0644\u0636\u0627\u062d\u064a\u0629 \u0627\u0644\u062c\u0646\u0648\u0628\u064a\u0629",),
    "\u0631\u0627\u0633 \u0627\u0644\u0646\u0627\u0642\u0648\u0631\u0629": ("\u0631\u0623\u0633 \u0627\u0644\u0646\u0627\u0642\u0648\u0631\u0629",),
    "\u0645\u0631\u063a\u0644\u064a\u0648\u062a": ("\u0645\u0631\u062c\u0644\u064a\u0648\u062a",),
    "\u064a\u062d\u0645\u0631": ("\u064a\u062d\u0645\u0631 \u0627\u0644\u0634\u0642\u064a\u0641",),
    "\u0627\u0641\u064a\u0641\u064a\u0645": ("\u0623\u0641\u064a\u0641\u064a\u0645",),
    "\u0627\u062f\u0645\u064a\u062a": ("\u0623\u062f\u0645\u064a\u062a",),
    "\u0645\u0639\u0627\u0644\u0648\u062a \u062a\u0631\u0634\u064a\u062d\u0627": ("\u0645\u0639\u0644\u0648\u062a \u062a\u0631\u0634\u064a\u062d\u0627",),
    "\u062a\u0644 \u0627\u0628\u064a\u0628": ("\u062a\u0644 \u0623\u0628\u064a\u0628 \u2013 \u064a\u0627\u0641\u0627",),
}

CHANNEL_LOCATION_PREFERRED_GOVERNORATE = {
    "\u0627\u0644\u0637\u064a\u0628\u0629": ("nabat", "\u0627\u0644\u0646\u0628\u0637\u064a\u0629"),
    "\u0637\u064a\u0628\u0629": ("nabat", "\u0627\u0644\u0646\u0628\u0637\u064a\u0629"),
    "\u0627\u0644\u0645\u0637\u0644\u0629": ("northern district", "\u0627\u0644\u0645\u0646\u0637\u0642\u0629 \u0627\u0644\u0634\u0645\u0627\u0644\u064a\u0629"),
    "\u0645\u0637\u0644\u0629": ("northern district", "\u0627\u0644\u0645\u0646\u0637\u0642\u0629 \u0627\u0644\u0634\u0645\u0627\u0644\u064a\u0629"),
    "\u0642\u0628\u0631\u064a\u062e\u0627": ("\u0645\u062d\u0627\u0641\u0638\u0629 \u0627\u0644\u0646\u0628\u0637\u064a\u0629",),
    "\u0639\u0631\u0628 \u0635\u0627\u0644\u064a\u0645": ("\u0645\u062d\u0627\u0641\u0638\u0629 \u0627\u0644\u0646\u0628\u0637\u064a\u0629",),
    "\u0639\u0631\u0628\u0635\u0627\u0644\u064a\u0645": ("\u0645\u062d\u0627\u0641\u0638\u0629 \u0627\u0644\u0646\u0628\u0637\u064a\u0629",),
    "\u0627\u0644\u0628\u064a\u0627\u0636\u0629": ("nabat", "\u0627\u0644\u0646\u0628\u0637\u064a\u0629", "south", "\u0627\u0644\u062c\u0646\u0648\u0628"),
    "\u0628\u064a\u0627\u0636\u0629": ("nabat", "\u0627\u0644\u0646\u0628\u0637\u064a\u0629", "south", "\u0627\u0644\u062c\u0646\u0648\u0628"),
}

LOCATION_PART_SUFFIXES = {
    "\u0627\u0644\u0639\u064a\u0646",
    "\u0639\u064a\u0646",
    "\u0627\u0644\u0641\u0648\u0642\u0627",
    "\u0641\u0648\u0642\u0627",
    "\u0627\u0644\u062a\u062d\u062a\u0627",
    "\u062a\u062d\u062a\u0627",
    "\u0627\u0644\u062d\u0648\u0634",
    "\u0627\u0644\u062d\u0627\u0631\u0629",
}

GENERIC_LOCATION_EXCLUSIONS = {
    "\u0627\u0644\u062c\u0648\u0627\u0631",
    "\u0641\u064a \u0627\u0644\u062c\u0648\u0627\u0631",
}

MANUAL_LOCATION_OVERRIDES = {
    "\u0627\u0644\u062e\u0627\u0646\u0648\u0642": {
        "name_ar": "\u0627\u0644\u062e\u0627\u0646\u0648\u0642",
        "name_en": "El Khanouq Border Area",
        "alt_names": ["El Khanouq", "Al Khanouq", "\u0627\u0644\u062e\u0627\u0646\u0648\u0642"],
        "governorate": "Northern District (Israel)",
        "latitude": 33.10611,
        "longitude": 35.49278,
    },
    "\u0627\u0644\u0645\u0646\u0627\u0631\u0629": {
        "name_ar": "\u0627\u0644\u0645\u0646\u0627\u0631\u0629",
        "name_en": "Menara",
        "alt_names": ["Menara", "Manara", "Al Manara", "Al Manarah", "\u0627\u0644\u0645\u0646\u0627\u0631\u0629"],
        "governorate": "Northern District (Israel)",
        "latitude": 33.19691,
        "longitude": 35.54393,
    },
    "\u064a\u062d\u0645\u0631 \u0627\u0644\u0634\u0642\u064a\u0641": {
        "name_ar": "\u064a\u062d\u0645\u0631 \u0627\u0644\u0634\u0642\u064a\u0641",
        "name_en": "Yohmor al-Shaqif",
        "alt_names": ["\u064a\u062d\u0645\u0631", "\u064a\u062d\u0645\u0631 \u0634\u0642\u064a\u0641", "\u064a\u062d\u0645\u0631_\u0627\u0644\u0634\u0642\u064a\u0641"],
        "governorate": "Nabatieh",
        "latitude": 33.30972,
        "longitude": 35.51694,
    },
}

CONTEXTUAL_LOCATION_REWRITE_RULES: tuple[tuple[set[str], dict[str, str | None]], ...] = (
    (
        {"\u064a\u062d\u0645\u0631", "\u0634\u0642\u064a\u0641"},
        {
            "\u064a\u062d\u0645\u0631": "\u064a\u062d\u0645\u0631 \u0627\u0644\u0634\u0642\u064a\u0641",
            "\u0634\u0642\u064a\u0641": None,
        },
    ),
    (
        {"\u0628\u0646\u062a", "\u062c\u0628\u064a\u0644"},
        {
            "\u0628\u0646\u062a": "\u0628\u0646\u062a \u062c\u0628\u064a\u0644",
            "\u062c\u0628\u064a\u0644": None,
        },
    ),
    (
        {"\u062f\u064a\u0631", "\u0633\u0631\u064a\u0627\u0646"},
        {
            "\u062f\u064a\u0631": "\u062f\u064a\u0631 \u0633\u0631\u064a\u0627\u0646",
            "\u0633\u0631\u064a\u0627\u0646": None,
        },
    ),
)


def _parse_alt_names(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return []


def _build_alias_map(session: Session) -> dict[str, list[AliasCandidate]]:
    alias_map: dict[str, list[AliasCandidate]] = {}
    locations = session.scalars(select(Location)).all()
    for location in locations:
        primary_name = normalize_hashtag(location.name_ar)
        if primary_name in GENERIC_LOCATION_EXCLUSIONS:
            continue
        aliases = [(location.name_ar, True), *((alias, False) for alias in _parse_alt_names(location.alt_names))]
        for alias, is_primary in aliases:
            normalized = normalize_hashtag(alias)
            if not normalized or normalized in GENERIC_LOCATION_EXCLUSIONS:
                continue
            bucket = alias_map.setdefault(normalized, [])
            if any(existing.location.id == location.id and existing.is_primary == is_primary for existing in bucket):
                continue
            bucket.append(AliasCandidate(location=location, is_primary=is_primary))
    return alias_map


def _governorate_priority(location: Location) -> int:
    governorate = normalize_hashtag(location.governorate or "").lower()
    return 1 if any(marker in governorate for marker in PREFERRED_GOVERNORATE_MARKERS) else 0


def _candidate_lookup_keys(candidate: str, seen_variants: set[str] | None = None) -> list[str]:
    normalized = normalize_hashtag(candidate)
    if not normalized or normalized in GENERIC_LOCATION_EXCLUSIONS:
        return []
    if seen_variants is None:
        seen_variants = set()
    if normalized in seen_variants:
        return []
    seen_variants.add(normalized)

    variants: list[str] = [normalized]
    words = normalized.split()
    if len(words) >= 3 and words[-1] in LOCATION_PART_SUFFIXES:
        variants.append(" ".join(words[:-1]))
    if len(words) >= 3:
        variants.append(" ".join(words[:-1]))

    keys: list[str] = []
    for variant in variants:
        if not variant:
            continue
        keys.append(variant)
        if variant.startswith("\u0627\u0644") and len(variant) > 2:
            keys.append(variant.removeprefix("\u0627\u0644").strip())
        elif not variant.startswith("\u0627\u0644"):
            keys.append(f"\u0627\u0644{variant}")

        for alias in CHANNEL_LOCATION_ALIASES.get(variant, ()):
            keys.extend(_candidate_lookup_keys(alias, seen_variants))

    return list(dict.fromkeys(key for key in keys if key))


def _resolve_alias(candidates: list[AliasCandidate]) -> Location | None:
    if not candidates:
        return None

    unique_locations = {candidate.location.id: candidate.location for candidate in candidates}
    if len(unique_locations) == 1:
        return next(iter(unique_locations.values()))

    primary_matches = {candidate.location.id: candidate.location for candidate in candidates if candidate.is_primary}
    if len(primary_matches) == 1:
        return next(iter(primary_matches.values()))

    preferred_primary = {
        candidate.location.id: candidate.location
        for candidate in candidates
        if candidate.is_primary and _governorate_priority(candidate.location) > 0
    }
    if len(preferred_primary) == 1:
        return next(iter(preferred_primary.values()))

    preferred_locations = {
        candidate.location.id: candidate.location
        for candidate in candidates
        if _governorate_priority(candidate.location) > 0
    }
    if len(preferred_locations) == 1:
        return next(iter(preferred_locations.values()))

    return None


def _ensure_manual_override(session: Session, normalized_candidate: str) -> Location | None:
    override = MANUAL_LOCATION_OVERRIDES.get(normalized_candidate)
    if override is None:
        return None

    existing = session.scalar(
        select(Location).where(
            Location.name_ar == override["name_ar"],
            Location.governorate == override["governorate"],
        )
    )
    if existing is not None:
        return existing

    location = Location(
        name_ar=override["name_ar"],
        name_en=override["name_en"],
        alt_names=json.dumps(override["alt_names"], ensure_ascii=False),
        governorate=override["governorate"],
        latitude=float(override["latitude"]),
        longitude=float(override["longitude"]),
        source="manual",
        feature_class="place",
        feature_code="locality",
    )
    session.add(location)
    session.flush()
    return location


def _contextual_location_rewrites(candidate_locations: list[str]) -> dict[str, str | None]:
    normalized_candidates: set[str] = set()
    for candidate in candidate_locations:
        normalized = normalize_hashtag(candidate)
        if normalized:
            normalized_candidates.add(normalized)

    rewrites: dict[str, str | None] = {}
    for required_candidates, mapping in CONTEXTUAL_LOCATION_REWRITE_RULES:
        if required_candidates.issubset(normalized_candidates):
            for candidate, rewritten in mapping.items():
                if candidate in normalized_candidates:
                    rewrites[candidate] = rewritten
    return rewrites


def _resolve_alias_for_candidate(candidate_name: str, candidates: list[AliasCandidate]) -> Location | None:
    location = _resolve_alias(candidates)
    if location is not None:
        return location

    normalized_candidate = normalize_hashtag(candidate_name)
    preferred_markers = CHANNEL_LOCATION_PREFERRED_GOVERNORATE.get(normalized_candidate)
    if not preferred_markers:
        return None

    preferred_locations = {
        candidate.location.id: candidate.location
        for candidate in candidates
        if any(marker in normalize_hashtag(candidate.location.governorate or "").lower() for marker in preferred_markers)
    }
    if len(preferred_locations) == 1:
        return next(iter(preferred_locations.values()))

    return None


def match_locations(session: Session, candidate_locations: list[str]) -> LocationMatchResult:
    alias_map = _build_alias_map(session)
    contextual_rewrites = _contextual_location_rewrites(candidate_locations)
    matches: list[MatchedLocation] = []
    unmatched: list[str] = []
    seen_location_ids: set[str] = set()

    for candidate in candidate_locations:
        candidate_for_match = candidate
        normalized_candidate = normalize_hashtag(candidate_for_match)
        rewritten_candidate = contextual_rewrites.get(normalized_candidate)
        if rewritten_candidate is None and normalized_candidate in contextual_rewrites:
            continue
        if rewritten_candidate:
            candidate_for_match = rewritten_candidate
            normalized_candidate = normalize_hashtag(candidate_for_match)

        manual_override = _ensure_manual_override(session, normalized_candidate)
        if manual_override is not None:
            if manual_override.id in seen_location_ids:
                continue
            matches.append(MatchedLocation(source_name=candidate_for_match, location=manual_override))
            seen_location_ids.add(manual_override.id)
            continue

        alias_candidates: list[AliasCandidate] = []
        for key in _candidate_lookup_keys(candidate_for_match):
            alias_candidates.extend(alias_map.get(key, []))
        location = _resolve_alias_for_candidate(candidate_for_match, alias_candidates)
        if location is None:
            unmatched.append(candidate_for_match)
            continue
        if location.id in seen_location_ids:
            continue
        matches.append(MatchedLocation(source_name=candidate_for_match, location=location))
        seen_location_ids.add(location.id)

    return LocationMatchResult(matches=matches, unmatched=unmatched)
