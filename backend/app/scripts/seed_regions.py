from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import Base, SessionLocal, engine
from app.models.region import Region


def load_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if payload.get("type") == "FeatureCollection":
        features = payload.get("features", [])
        if not features:
            raise ValueError("GeoJSON FeatureCollection has no features")
        return features[0]
    if payload.get("type") == "Feature":
        return payload
    if payload.get("type") in {"Polygon", "MultiPolygon"}:
        return {"type": "Feature", "properties": {}, "geometry": payload}
    raise ValueError("Unsupported GeoJSON payload")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed regions into SQLite")
    parser.add_argument("--path", default="data/south_lebanon.geojson", help="Path to the region GeoJSON file")
    parser.add_argument("--slug", default="south-lebanon")
    parser.add_argument("--name", default="South Lebanon")
    parser.add_argument("--skip-if-exists", action="store_true", help="Skip seeding if region already exists")
    args = parser.parse_args()

    seed_path = Path(args.path)
    if not seed_path.is_absolute():
        seed_path = (Path(__file__).resolve().parents[2] / seed_path).resolve()

    feature = load_geojson(seed_path)
    feature.setdefault("properties", {})
    feature["properties"]["slug"] = args.slug
    feature["properties"]["name"] = args.name

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        region = session.scalar(select(Region).where(Region.slug == args.slug))
        if args.skip_if_exists and region is not None:
            print(f"Region '{args.slug}' already exists, skipping")
            return
        if region is None:
            region = Region(slug=args.slug, name=args.name, geojson="")
            session.add(region)

        region.name = args.name
        region.geojson = json.dumps(feature, ensure_ascii=False)
        session.commit()
        print(f"Seeded region '{args.slug}' from {seed_path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
