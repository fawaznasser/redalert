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
    "\u0639\u0644\u0645\u0627\u0646 \u0645\u0631\u062c\u0639\u064a\u0648\u0646": ("\u0645\u0631\u062c\u0639\u064a\u0648\u0646",),
    "\u0637\u064a\u0628\u0629": ("\u0627\u0644\u0637\u064a\u0628\u0629",),
    "\u0642\u0644\u0648\u064a\u0647": ("\u0642\u0644\u0648\u064a\u0629",),
}

CHANNEL_LOCATION_PREFERRED_GOVERNORATE = {
    "\u0627\u0644\u0637\u064a\u0628\u0629": ("nabat", "\u0627\u0644\u0646\u0628\u0637\u064a\u0629"),
    "\u0637\u064a\u0628\u0629": ("nabat", "\u0627\u0644\u0646\u0628\u0637\u064a\u0629"),
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
        aliases = [(location.name_ar, True), *((alias, False) for alias in _parse_alt_names(location.alt_names))]
        for alias, is_primary in aliases:
            normalized = normalize_hashtag(alias)
            if not normalized:
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
    if not normalized:
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
    matches: list[MatchedLocation] = []
    unmatched: list[str] = []
    seen_location_ids: set[str] = set()

    for candidate in candidate_locations:
        alias_candidates: list[AliasCandidate] = []
        for key in _candidate_lookup_keys(candidate):
            alias_candidates.extend(alias_map.get(key, []))
        location = _resolve_alias_for_candidate(candidate, alias_candidates)
        if location is None:
            unmatched.append(candidate)
            continue
        if location.id in seen_location_ids:
            continue
        matches.append(MatchedLocation(source_name=candidate, location=location))
        seen_location_ids.add(location.id)

    return LocationMatchResult(matches=matches, unmatched=unmatched)
