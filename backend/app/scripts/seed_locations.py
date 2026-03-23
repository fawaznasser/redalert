from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import Base, SessionLocal, engine
from app.models.location import Location
from app.services.parser import normalize_hashtag


def load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, list):
        return data
    raise ValueError("Location seed file must contain a list of rows")


def as_float(value) -> float:
    return float(value) if value is not None and value != "" else 0.0


def as_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def find_existing_location(session, *, geoname_id: int | None, name_ar: str, district: str | None, governorate: str | None) -> Location | None:
    if geoname_id is not None:
        location = session.scalar(select(Location).where(Location.geoname_id == geoname_id))
        if location is not None:
            return location

    normalized_name = normalize_hashtag(name_ar)
    candidates = session.scalars(select(Location).where(Location.name_ar == name_ar)).all()
    if district or governorate:
        for candidate in candidates:
            if candidate.district == district and candidate.governorate == governorate:
                return candidate
    if candidates:
        return candidates[0]

    all_candidates = session.scalars(select(Location)).all()
    for candidate in all_candidates:
        if normalize_hashtag(candidate.name_ar) == normalized_name:
            if district and candidate.district and candidate.district != district:
                continue
            if governorate and candidate.governorate and candidate.governorate != governorate:
                continue
            return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed locations into SQLite")
    parser.add_argument("--path", default="data/locations.sample.json", help="Path to the locations JSON/CSV file")
    parser.add_argument("--skip-if-exists", action="store_true", help="Skip seeding if locations already exist")
    args = parser.parse_args()

    seed_path = Path(args.path)
    if not seed_path.is_absolute():
        seed_path = (Path(__file__).resolve().parents[2] / seed_path).resolve()

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        existing_count = session.scalar(select(func.count(Location.id))) or 0
        if args.skip_if_exists and existing_count:
            print(f"Locations already exist ({existing_count}), skipping")
            return

        rows = load_rows(seed_path)
        upserted = 0
        for row in rows:
            name_ar = str(row.get("name_ar", "")).strip()
            if not name_ar:
                continue

            district = str(row.get("district")).strip() if row.get("district") else None
            governorate = str(row.get("governorate")).strip() if row.get("governorate") else None
            geoname_id = as_int(row.get("geoname_id"))

            alt_names = row.get("alt_names")
            if alt_names is None:
                alt_names_json = None
            elif isinstance(alt_names, str):
                alt_names_json = alt_names if alt_names.strip().startswith("[") else json.dumps([alt_names], ensure_ascii=False)
            else:
                alt_names_json = json.dumps(list(alt_names), ensure_ascii=False)

            location = find_existing_location(
                session,
                geoname_id=geoname_id,
                name_ar=name_ar,
                district=district,
                governorate=governorate,
            )
            if location is None:
                location = Location(name_ar=name_ar, latitude=0.0, longitude=0.0)
                session.add(location)

            location.geoname_id = geoname_id
            location.source = str(row.get("source")).strip() if row.get("source") else (location.source or "manual")
            location.feature_class = str(row.get("feature_class")).strip() if row.get("feature_class") else None
            location.feature_code = str(row.get("feature_code")).strip() if row.get("feature_code") else None
            location.name_en = str(row.get("name_en")).strip() if row.get("name_en") else None
            location.alt_names = alt_names_json
            location.district = district
            location.governorate = governorate
            location.latitude = as_float(row.get("latitude", row.get("lat")))
            location.longitude = as_float(row.get("longitude", row.get("lon")))
            upserted += 1

        session.commit()
        print(f"Seeded {upserted} locations from {seed_path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
