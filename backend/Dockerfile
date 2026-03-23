FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python app/scripts/seed_regions.py --skip-if-exists && python app/scripts/seed_locations.py --path data/lebanon_named_locations.json --skip-if-exists && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
