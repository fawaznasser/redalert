from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import Base
from app.models.region import Region
from app.schemas.common import EventType, LocationMode
from app.services.event_service import ingest_message


class StickerFighterOcrTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        self.Session = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session = self.Session()
        self.session.add(
            Region(
                slug="south-lebanon",
                name="South Lebanon",
                geojson='{"type":"FeatureCollection","features":[]}',
            )
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_sticker_ocr_text_creates_fighter_threat(self) -> None:
        result = ingest_message(
            self.session,
            telegram_message_id="ocr-sticker-1",
            channel_name="redlinkleb",
            message_text="حربي بالأجواء - حيطة وحذر",
            message_date=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            raw_payload={"_ocr": {"media_kind": "sticker", "text": "حربي بالأجواء - حيطة وحذر"}},
        )

        self.assertEqual(result.parsed_message.event_type, EventType.fighter_jet_movement)
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event.event_type, EventType.fighter_jet_movement.value)
        self.assertEqual(event.location_mode, LocationMode.regional.value)
        self.assertIsNone(event.location_id)
        self.assertIsNotNone(event.region_id)

    def test_green_label_with_incursion_text_creates_incursion_event_for_rnn_source(self) -> None:
        result = ingest_message(
            self.session,
            telegram_message_id="ocr-green-1",
            channel_name="RNN_Alerts_AR_Lebanon",
            message_text="تم رصد توغل بري في لبنان\n\nالمناطق المتأثرة: #كريات_شمونة",
            message_date=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
            raw_payload={"_ocr": {"media_kind": "image", "label_color": "green"}},
        )

        self.assertIsNotNone(result.parsed_message)
        assert result.parsed_message is not None
        self.assertEqual(result.parsed_message.event_type, EventType.ground_incursion)
        self.assertIn("كريات شمونة", result.parsed_message.candidate_locations)

    def test_green_label_without_incursion_text_creates_incursion_event(self) -> None:
        result = ingest_message(
            self.session,
            telegram_message_id="ocr-green-2",
            channel_name="RNN_Alerts_AR_Lebanon",
            message_text="#كريات_شمونة",
            message_date=datetime(2026, 4, 1, 10, 6, tzinfo=timezone.utc),
            raw_payload={"_ocr": {"media_kind": "image", "label_color": "green"}},
        )

        self.assertIsNotNone(result.parsed_message)
        assert result.parsed_message is not None
        self.assertEqual(result.parsed_message.event_type, EventType.ground_incursion)

    def test_green_label_with_non_incursion_text_forces_incursion(self) -> None:
        result = ingest_message(
            self.session,
            telegram_message_id="ocr-green-3",
            channel_name="RNN_Alerts_AR_Lebanon",
            message_text="تم رصد تحليق مسيّرات في لبنان\n\nالمناطق المتأثرة: #كريات_شمونة",
            message_date=datetime(2026, 4, 1, 10, 7, tzinfo=timezone.utc),
            raw_payload={"_ocr": {"media_kind": "image", "label_color": "green"}},
        )

        self.assertIsNotNone(result.parsed_message)
        assert result.parsed_message is not None
        self.assertEqual(result.parsed_message.event_type, EventType.ground_incursion)

    def test_incursion_text_without_green_label_does_not_stay_incursion(self) -> None:
        result = ingest_message(
            self.session,
            telegram_message_id="ocr-green-4",
            channel_name="RNN_Alerts_AR_Lebanon",
            message_text="تم رصد توغل بري في لبنان\n\nالمناطق المتأثرة: القنطرة",
            message_date=datetime(2026, 4, 1, 10, 8, tzinfo=timezone.utc),
            raw_payload={"_ocr": {"media_kind": "image", "label_color": "red"}},
        )

        self.assertIsNotNone(result.parsed_message)
        assert result.parsed_message is not None
        self.assertNotEqual(result.parsed_message.event_type, EventType.ground_incursion)


if __name__ == "__main__":
    unittest.main()
