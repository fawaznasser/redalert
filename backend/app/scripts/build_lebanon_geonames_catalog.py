from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
import sys
import zipfile

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.parser import normalize_hashtag

ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF]")
EXCLUDED_FEATURE_CODES = {"PPLH", "PPLQ", "PPLW", "PPLCH"}


def contains_arabic(value: str) -> bool:
    return bool(ARABIC_PATTERN.search(value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full-country Lebanon named-locations catalog from GeoNames.")
    parser.add_argument("--geonames-zip", default="data/geonames/LB.zip", help="Path to the GeoNames Lebanon country dump ZIP")
    parser.add_argument(
        "--alternates-zip",
        default="data/geonames/LB-alternatenames.zip",
        help="Path to the GeoNames Lebanon alternate names ZIP",
    )
    parser.add_argument("--admin1", default="data/geonames/admin1CodesASCII.txt", help="Path to GeoNames admin1 codes")
    parser.add_argument("--admin2", default="data/geonames/admin2Codes.txt", help="Path to GeoNames admin2 codes")
    parser.add_argument(
        "--output",
        default="data/lebanon_named_locations.json",
        help="Path to write the generated Lebanon locations JSON catalog",
    )
    return parser.parse_args()


def resolve_input(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def load_admin_map(path: Path, *, prefix: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            code = row[0].strip()
            name = row[1].strip()
            if not code.startswith(prefix) or not name:
                continue
            mapping[code] = name
    return mapping


def load_alternate_names(path: Path) -> dict[int, list[str]]:
    aliases: dict[int, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        with archive.open("LB.txt") as handle:
            for raw_line in handle:
                row = raw_line.decode("utf-8").rstrip("\n").split("\t")
                if len(row) < 4:
                    continue
                geoname_id = int(row[1])
                language = row[2].strip()
                name = row[3].strip()
                if not name:
                    continue
                if language == "ar" or contains_arabic(name):
                    aliases.setdefault(geoname_id, []).append(name)
    return aliases


def is_current_populated_place(feature_class: str, feature_code: str) -> bool:
    return feature_class == "P" and feature_code not in EXCLUDED_FEATURE_CODES


def unique_names(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        normalized = normalize_hashtag(stripped)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(stripped)
    return unique


def split_row_alternate_names(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def build_catalog(
    *,
    geonames_zip: Path,
    alternates_zip: Path,
    admin1_path: Path,
    admin2_path: Path,
) -> list[dict]:
    admin1_map = load_admin_map(admin1_path, prefix="LB.")
    admin2_map = load_admin_map(admin2_path, prefix="LB.")
    arabic_alternates = load_alternate_names(alternates_zip)

    rows: list[dict] = []
    with zipfile.ZipFile(geonames_zip) as archive:
        with archive.open("LB.txt") as handle:
            for raw_line in handle:
                row = raw_line.decode("utf-8").rstrip("\n").split("\t")
                if len(row) < 19:
                    continue

                geoname_id = int(row[0])
                name = row[1].strip()
                ascii_name = row[2].strip()
                alternatenames = row[3].strip()
                latitude = float(row[4])
                longitude = float(row[5])
                feature_class = row[6].strip()
                feature_code = row[7].strip()
                admin1_code = row[10].strip()
                admin2_code = row[11].strip()

                if not is_current_populated_place(feature_class, feature_code):
                    continue

                governorate = admin1_map.get(f"LB.{admin1_code}") if admin1_code else None
                district = admin2_map.get(f"LB.{admin1_code}.{admin2_code}") if admin1_code and admin2_code else None

                row_alt_names = split_row_alternate_names(alternatenames)
                arabic_names = unique_names(
                    [
                        *arabic_alternates.get(geoname_id, []),
                        *[item for item in row_alt_names if contains_arabic(item)],
                        name if contains_arabic(name) else "",
                    ]
                )
                latin_names = unique_names(
                    [
                        name,
                        ascii_name,
                        *[item for item in row_alt_names if not contains_arabic(item)],
                    ]
                )

                canonical_ar = arabic_names[0] if arabic_names else (name or ascii_name)
                alt_names = unique_names(
                    [
                        *arabic_names[1:],
                        *latin_names,
                    ]
                )
                name_en = ascii_name or name or None

                rows.append(
                    {
                        "geoname_id": geoname_id,
                        "source": "geonames",
                        "feature_class": feature_class,
                        "feature_code": feature_code,
                        "name_ar": canonical_ar,
                        "name_en": name_en,
                        "alt_names": alt_names,
                        "district": district,
                        "governorate": governorate,
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                )

    rows.sort(key=lambda item: (normalize_hashtag(item["name_ar"]), item["district"] or "", item["geoname_id"]))
    return rows


def main() -> None:
    args = parse_args()
    geonames_zip = resolve_input(args.geonames_zip)
    alternates_zip = resolve_input(args.alternates_zip)
    admin1_path = resolve_input(args.admin1)
    admin2_path = resolve_input(args.admin2)
    output_path = resolve_input(args.output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_catalog(
        geonames_zip=geonames_zip,
        alternates_zip=alternates_zip,
        admin1_path=admin1_path,
        admin2_path=admin2_path,
    )

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)

    print(f"Built {len(rows)} Lebanon named locations into {output_path}")


if __name__ == "__main__":
    main()
