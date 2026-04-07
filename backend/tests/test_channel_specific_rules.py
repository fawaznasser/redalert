from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.schemas.common import EventType
from app.services import event_service


class ChannelSpecificRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_primary = settings.telegram_channel
        self.original_secondary = settings.telegram_secondary_channel

    def tearDown(self) -> None:
        settings.telegram_channel = self.original_primary
        settings.telegram_secondary_channel = self.original_secondary

    def test_rnn_primary_channel_keeps_ground_incursion(self) -> None:
        settings.telegram_channel = "RNN_Alerts_AR_Lebanon"
        settings.telegram_secondary_channel = "t.me/alichoeib1970"

        result = event_service._filter_event_type_for_channel("RNN_Alerts_AR_Lebanon", EventType.ground_incursion)

        self.assertEqual(result, EventType.ground_incursion)

    def test_redlink_channel_still_drops_ground_incursion(self) -> None:
        settings.telegram_channel = "redlinkleb"
        settings.telegram_secondary_channel = None

        result = event_service._filter_event_type_for_channel("redlinkleb", EventType.ground_incursion)

        self.assertIsNone(result)

    def test_secondary_channel_keeps_attack_events(self) -> None:
        settings.telegram_channel = "RNN_Alerts_AR_Lebanon"
        settings.telegram_secondary_channel = "t.me/alichoeib1970"

        result = event_service._filter_event_type_for_channel("alichoeib1970", EventType.fighter_jet_movement)

        self.assertEqual(result, EventType.fighter_jet_movement)

    def test_secondary_channel_uses_general_parser_for_enemy_attack_text(self) -> None:
        settings.telegram_channel = "RNN_Alerts_AR_Lebanon"
        settings.telegram_secondary_channel = "t.me/alichoeib1970"

        parsed = event_service._parse_message_for_channel(
            "alichoeib1970",
            "مراسل المنار :\n\nقصف مدفعي صهيوني يستهدف اطراف بلدتي القليلة والحنية ووادي العزية",
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type, EventType.fighter_jet_movement)
        self.assertTrue(parsed.candidate_locations)

    def test_rnn_primary_channel_keeps_attack_side(self) -> None:
        settings.telegram_channel = "RNN_Alerts_AR_Lebanon"
        event = SimpleNamespace(
            raw_message=SimpleNamespace(
                channel_name="RNN_Alerts_AR_Lebanon",
                raw_json='{"_ocr":{"attack_side":"resistance_attack"}}',
            )
        )

        result = event_service.get_event_attack_side(event)

        self.assertEqual(result, "resistance_attack")

    def test_redlink_attack_side_remains_hidden(self) -> None:
        settings.telegram_channel = "redlinkleb"
        event = SimpleNamespace(
            raw_message=SimpleNamespace(
                channel_name="redlinkleb",
                raw_json='{"_ocr":{"attack_side":"enemy_attack"}}',
            )
        )

        result = event_service.get_event_attack_side(event)

        self.assertIsNone(result)

    def test_rnn_airstrike_text_infers_enemy_attack_side(self) -> None:
        event = SimpleNamespace(
            source_text="تم رصد غارة جوية في لبنان\n\nالمناطق المتأثرة: بنت جبيل",
            latitude=33.12,
            longitude=35.44,
            raw_message=SimpleNamespace(
                channel_name="RNN_Alerts_AR_Lebanon",
                message_text="تم رصد غارة جوية في لبنان\n\nالمناطق المتأثرة: بنت جبيل",
                raw_json=None,
            ),
        )

        result = event_service.get_event_attack_side(event)

        self.assertEqual(result, "enemy_attack")

    def test_rnn_resistance_operation_text_infers_resistance_attack_side(self) -> None:
        event = SimpleNamespace(
            source_text="تم رصد هجوم بطائرات مسيّرة في لبنان\nاستهداف تجمع لجنود الاحتلال بمسيّرة انقضاضيّة",
            latitude=33.18,
            longitude=35.43,
            raw_message=SimpleNamespace(
                channel_name="RNN_Alerts_AR_Lebanon",
                message_text="تم رصد هجوم بطائرات مسيّرة في لبنان\nاستهداف تجمع لجنود الاحتلال بمسيّرة انقضاضيّة",
                raw_json=None,
            ),
        )

        result = event_service.get_event_attack_side(event)

        self.assertEqual(result, "resistance_attack")

    def test_actual_incursion_text_stays_separate_from_attack_side(self) -> None:
        event = SimpleNamespace(
            source_text="تم رصد توغل بري في لبنان\n\nالمناطق المتأثرة: الناقورة",
            latitude=33.12,
            longitude=35.11,
            raw_message=SimpleNamespace(
                channel_name="RNN_Alerts_AR_Lebanon",
                message_text="تم رصد توغل بري في لبنان\n\nالمناطق المتأثرة: الناقورة",
                raw_json=None,
            ),
        )

        result = event_service.get_event_attack_side(event)

        self.assertIsNone(result)

    def test_israel_location_metadata_forces_resistance_attack_side(self) -> None:
        event = SimpleNamespace(
            source_text="تم رصد هجوم بطائرات مسيّرة في لبنان\nتسلل مسيرات نحو كريات شمونة",
            latitude=33.2121315,
            longitude=35.5715923,
            location=SimpleNamespace(
                governorate="Northern District (Israel)",
                district=None,
                name_en="Kiryat Shmona",
            ),
            raw_message=SimpleNamespace(
                channel_name="RNN_Alerts_AR_Lebanon",
                message_text="تم رصد هجوم بطائرات مسيّرة في لبنان\nتسلل مسيرات نحو كريات شمونة",
                raw_json=None,
            ),
        )

        result = event_service.get_event_attack_side(event)

        self.assertEqual(result, "resistance_attack")

    def test_redlink_repost_filter_is_redlink_specific(self) -> None:
        self.assertTrue(event_service._channel_filters_include_redlink(["redlinkleb"]))
        self.assertFalse(event_service._channel_filters_include_redlink(["RNN_Alerts_AR_Lebanon", "alichoeib1970"]))


if __name__ == "__main__":
    unittest.main()
