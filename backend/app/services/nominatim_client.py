from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.location import Location
from app.services.parser import normalize_hashtag

logger = logging.getLogger(__name__)

LEBANON_VIEWBOX = "35.08,34.70,36.65,33.02"
PLACE_KEYS = (
    "city",
    "town",
    "village",
    "hamlet",
    "suburb",
    "neighbourhood",
    "municipality",
    "county",
)
ACCEPTED_OSM_CLASSES = {"place", "boundary"}
ACCEPTED_OSM_TYPES = {
    "city",
    "town",
    "village",
    "hamlet",
    "suburb",
    "neighbourhood",
    "residential",
    "administrative",
    "municipality",
    "locality",
}
_LAST_REQUEST_AT = 0.0


@dataclass(slots=True)
class NominatimResult:
    query_name: str
    name_ar: str
    name_en: str | None
    latitude: float
    longitude: float
    governorate: str | None
    district: str | None
    alt_names: list[str]
    source_ref: str
    osm_class: str | None
    osm_type: str | None


def _rate_limit() -> None:
    global _LAST_REQUEST_AT
    elapsed = time.monotonic() - _LAST_REQUEST_AT
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _LAST_REQUEST_AT = time.monotonic()


def _request_json(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    query = urlencode(params)
    url = f"{settings.nominatim_base_url.rstrip('/')}{path}?{query}"
    headers = {"User-Agent": settings.nominatim_user_agent}
    if settings.nominatim_email:
        headers["From"] = settings.nominatim_email

    request = Request(url, headers=headers)
    _rate_limit()
    with urlopen(request, timeout=20) as response:  # noqa: S310
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _collect_alt_names(result: dict[str, Any], query_name: str) -> list[str]:
    values: list[str] = [query_name]
    namedetails = result.get("namedetails") or {}
    address = result.get("address") or {}

    for key in ("name", "name:ar", "name:en", "int_name", "official_name", "official_name:ar", "official_name:en"):
        value = namedetails.get(key)
        if value:
            values.append(str(value))

    for key in PLACE_KEYS:
        value = address.get(key)
        if value:
            values.append(str(value))

    display_name = result.get("display_name")
    if display_name:
        values.extend(part.strip() for part in str(display_name).split(",") if part.strip())

    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_hashtag(value)
        if not normalized or normalized in seen:
            continue
        unique.append(value.strip())
        seen.add(normalized)
    return unique


def _extract_arabic_name(result: dict[str, Any], query_name: str) -> str:
    namedetails = result.get("namedetails") or {}
    address = result.get("address") or {}

    for key in ("name:ar", "official_name:ar"):
        value = namedetails.get(key)
        if value:
            return str(value).strip()

    for key in PLACE_KEYS:
        value = address.get(key)
        if value and any("\u0600" <= character <= "\u06ff" for character in str(value)):
            return str(value).strip()

    return query_name.strip()


def _extract_english_name(result: dict[str, Any]) -> str | None:
    namedetails = result.get("namedetails") or {}
    for key in ("name:en", "official_name:en", "int_name", "name"):
        value = namedetails.get(key)
        if value:
            return str(value).strip()
    return None


def _score_result(result: dict[str, Any]) -> tuple[int, float]:
    osm_class = str(result.get("class") or "")
    osm_type = str(result.get("type") or "")
    class_score = 1 if osm_class in ACCEPTED_OSM_CLASSES and osm_type in ACCEPTED_OSM_TYPES else 0
    importance = float(result.get("importance") or 0.0)
    return class_score, importance


def search_nominatim(query_name: str) -> NominatimResult | None:
    if not settings.nominatim_enabled:
        return None

    results = _request_json(
        "/search",
        {
            "q": query_name,
            "format": "jsonv2",
            "countrycodes": settings.nominatim_country_codes,
            "addressdetails": 1,
            "namedetails": 1,
            "limit": settings.nominatim_limit,
            "bounded": 1,
            "viewbox": LEBANON_VIEWBOX,
        },
    )
    if not results:
        return None

    filtered = sorted(results, key=_score_result, reverse=True)
    best = filtered[0]
    address = best.get("address") or {}

    return NominatimResult(
        query_name=query_name,
        name_ar=_extract_arabic_name(best, query_name),
        name_en=_extract_english_name(best),
        latitude=float(best["lat"]),
        longitude=float(best["lon"]),
        governorate=address.get("state"),
        district=address.get("county"),
        alt_names=_collect_alt_names(best, query_name),
        source_ref=f"nominatim:{best.get('osm_type')}:{best.get('osm_id')}",
        osm_class=best.get("class"),
        osm_type=best.get("type"),
    )


def _load_alt_names(location: Location) -> list[str]:
    if not location.alt_names:
        return []
    try:
        payload = json.loads(location.alt_names)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if str(item).strip()]


def _save_alt_names(location: Location, alt_names: list[str]) -> None:
    unique: list[str] = []
    seen: set[str] = set()
    for value in alt_names:
        normalized = normalize_hashtag(value)
        if not normalized or normalized in seen:
            continue
        unique.append(value)
        seen.add(normalized)
    location.alt_names = json.dumps(unique, ensure_ascii=False)


def upsert_nominatim_location(session: Session, result: NominatimResult) -> Location:
    normalized_query = normalize_hashtag(result.query_name)
    candidates = session.scalars(select(Location)).all()

    for candidate in candidates:
        if normalize_hashtag(candidate.name_ar) == normalized_query:
            merged_alt_names = _load_alt_names(candidate) + result.alt_names
            candidate.name_en = candidate.name_en or result.name_en
            candidate.district = candidate.district or result.district
            candidate.governorate = candidate.governorate or result.governorate
            candidate.latitude = result.latitude
            candidate.longitude = result.longitude
            candidate.source = "nominatim"
            candidate.feature_class = result.osm_class
            candidate.feature_code = result.osm_type
            _save_alt_names(candidate, merged_alt_names)
            session.flush()
            return candidate

        for alias in _load_alt_names(candidate):
            if normalize_hashtag(alias) == normalized_query:
                merged_alt_names = _load_alt_names(candidate) + result.alt_names
                candidate.latitude = result.latitude
                candidate.longitude = result.longitude
                candidate.source = "nominatim"
                candidate.feature_class = result.osm_class
                candidate.feature_code = result.osm_type
                candidate.name_en = candidate.name_en or result.name_en
                candidate.district = candidate.district or result.district
                candidate.governorate = candidate.governorate or result.governorate
                _save_alt_names(candidate, merged_alt_names)
                session.flush()
                return candidate

    location = Location(
        name_ar=result.name_ar,
        name_en=result.name_en,
        district=result.district,
        governorate=result.governorate,
        latitude=result.latitude,
        longitude=result.longitude,
        source="nominatim",
        feature_class=result.osm_class,
        feature_code=result.osm_type,
    )
    _save_alt_names(location, result.alt_names)
    session.add(location)
    session.flush()
    return location

