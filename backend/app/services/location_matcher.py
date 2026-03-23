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
    "\u0645\u0641\u062f\u0648\u0646": ("\u0645\u064a\u0641\u062f\u0648\u0646",),
    "\u062a\u0648\u0644": ("\u0645\u0632\u0631\u0639\u0629 \u062a\u0648\u0644",),
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


def _candidate_lookup_keys(candidate: str) -> list[str]:
    normalized = normalize_hashtag(candidate)
    if not normalized:
        return []

    keys = [normalized]
    if normalized.startswith("\u0627\u0644") and len(normalized) > 2:
        keys.append(normalized.removeprefix("\u0627\u0644").strip())
    elif not normalized.startswith("\u0627\u0644"):
        keys.append(f"\u0627\u0644{normalized}")
    for alias in CHANNEL_LOCATION_ALIASES.get(normalized, ()):
        keys.extend(_candidate_lookup_keys(alias))
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


def match_locations(session: Session, candidate_locations: list[str]) -> LocationMatchResult:
    alias_map = _build_alias_map(session)
    matches: list[MatchedLocation] = []
    unmatched: list[str] = []
    seen_location_ids: set[str] = set()

    for candidate in candidate_locations:
        alias_candidates: list[AliasCandidate] = []
        for key in _candidate_lookup_keys(candidate):
            alias_candidates.extend(alias_map.get(key, []))
        location = _resolve_alias(alias_candidates)
        if location is None:
            unmatched.append(candidate)
            continue
        if location.id in seen_location_ids:
            continue
        matches.append(MatchedLocation(source_name=candidate, location=location))
        seen_location_ids.add(location.id)

    return LocationMatchResult(matches=matches, unmatched=unmatched)
