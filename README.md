# Telegram Red Zone Map Dashboard

SQLite MVP for ingesting Arabic Telegram alerts, storing every raw post, structuring matched air-activity events, and rendering them on a live map.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Telethon, SQLite
- Frontend: Next.js, React, TypeScript, Tailwind CSS, Leaflet
- Local orchestration: Docker Compose

## What It Does

- Stores every Telegram post in `raw_messages`
- Parses Arabic hashtags with a rule-based parser only
- Maps event tags to:
  - `#درون` -> `drone_movement`
  - `#مقاتلات_حربية` -> `fighter_jet_movement`
  - `#مروحي` -> `helicopter_movement`
- Treats remaining hashtags as candidate locations
- Creates one exact event per matched village/city
- Falls back to a South Lebanon regional event for fighter alerts with no matched location
- Returns exact events as points and regional events as polygon-backed overlays

## Project Layout

```text
backend/
  app/
    api/routes/
    models/
    schemas/
    services/
    scripts/
  alembic/
  data/
frontend/
  app/
  components/
  lib/
  types/
```

## Database Design

SQLite only.

- `locations` stores `latitude` / `longitude` numeric columns
- `regions` stores GeoJSON as text
- `events` stores copied point coordinates for exact events and keeps regional events coordinate-free

## Local Run

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
python app/scripts/seed_regions.py
python app/scripts/seed_locations.py
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`.

## Docker Compose

```bash
docker compose up --build
```

This starts:

- backend on `http://localhost:8000`
- frontend on `http://localhost:3000`

The compose flow runs migrations and seeds the sample South Lebanon region and sample locations automatically.

## Telegram Configuration

Set these in `backend/.env`:

```env
TELEGRAM_ENABLED=true
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_SESSION=...
TELEGRAM_CHANNEL=...
TELEGRAM_HISTORY_BACKFILL_LIMIT=50
TELEGRAM_POLL_INTERVAL_SECONDS=5
TELEGRAM_EDIT_SYNC_LIMIT=15
```

To generate a Telethon string session:

```bash
cd backend
python app/scripts/bootstrap_telegram_session.py
```

Paste the resulting session string into `TELEGRAM_SESSION`.

The Telegram pipeline now has three layers:

- live `NewMessage` events
- live `MessageEdited` events
- periodic recent-history polling every few seconds to catch anything missed while the listener reconnects

That means the website can update from Telegram without a manual browser refresh as long as the backend process is running.

## Seed Data

- `backend/data/locations.sample.json` contains a small village gazetteer for MVP/demo use
- `backend/data/lebanon_named_locations.json` is the generated full-country named-location catalog built from GeoNames
- `backend/data/south_lebanon.geojson` contains a simplified South Lebanon polygon for overlay rendering

Replace both with authoritative datasets before relying on this beyond prototype use.

### Build Full Lebanon Location Catalog

Download the GeoNames Lebanon source files into `backend/data/geonames/`, then run:

```bash
cd backend
python app/scripts/build_lebanon_geonames_catalog.py
python app/scripts/seed_locations.py --path data/lebanon_named_locations.json
python app/scripts/reprocess_recent_raw_messages.py --hours 72
```

This imports all current named populated locations in Lebanon from the GeoNames Lebanon dump and its Lebanon alternate-names dump.

### Enrich Unmatched Villages From OSM / Nominatim

If the Telegram channel uses a village spelling that is missing from the local catalog, you can geocode it from the same underlying OpenStreetMap-style geodata used by many map providers.

Enable Nominatim in `backend/.env`:

```env
NOMINATIM_ENABLED=true
NOMINATIM_USER_AGENT=red-alert-dashboard/1.0
NOMINATIM_EMAIL=you@example.com
```

Then run:

```bash
cd backend
python app/scripts/enrich_locations_from_nominatim.py --hours 72 --limit 25
python app/scripts/reprocess_recent_raw_messages.py --hours 72 --include-existing
```

You can also geocode a specific village name directly:

```bash
python app/scripts/enrich_locations_from_nominatim.py --name الحوش
```

This does not scrape map tiles. It queries Nominatim search results, stores the resolved latitude and longitude in `locations`, and then lets the normal matcher/event pipeline use those coordinates.

## API Endpoints

- `GET /health`
- `GET /events`
- `GET /events/map`
- `GET /stats`
- `GET /locations`
- `GET /regions`

## Acceptance Behavior

- Raw Telegram posts are stored even when they do not parse into structured events
- Drone and helicopter posts create one exact event per matched location hashtag
- Fighter posts without matched locations create a regional South Lebanon event
- Regional alerts do not get fake coordinates

## Notes

- The parser is rule-based only. No AI or fuzzy interpretation is used.
- SQLite is fine for this MVP, but it is not the right long-term choice for high-write or geospatial-heavy production workloads.
