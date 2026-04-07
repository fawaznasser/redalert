from __future__ import annotations

import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import Base
from app.models.location import Location
from app.services.location_matcher import match_locations
from app.services.parser import parse_message_text, parse_rnn_channel_message


class LocationFilterTests(unittest.TestCase):
    def test_parse_message_text_ignores_generic_al_jiwar(self) -> None:
        parsed = parse_message_text(
            "🤔⚠️ #مسير\n\n#سير_الغربية\nــــــــــــــــــــ الجوار\n\nحيطة وحذر 🚨🚨🚨"
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.candidate_locations, ["سير الغربية"])

    def test_parse_message_text_strips_affected_areas_label(self) -> None:
        parsed = parse_message_text("#مسير\nالمناطق المتاثرة: كريات شمونة")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.candidate_locations, ["كريات شمونة"])

    def test_parse_message_text_handles_rnn_airstrike_format(self) -> None:
        parsed = parse_message_text("تم رصد غارة جوية في لبنان  المناطق المتأثرة: الدوير، النبطية")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "fighter_jet_movement")
        self.assertEqual(parsed.candidate_locations, ["الدوير", "النبطية"])

    def test_parse_message_text_handles_rnn_artillery_format(self) -> None:
        parsed = parse_message_text("تم رصد قصف مدفعي في لبنان  المناطق المتأثرة: مارون الراس، بنت جبيل، جزين")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "fighter_jet_movement")
        self.assertEqual(parsed.candidate_locations, ["مارون الراس", "بنت جبيل", "جزين"])

    def test_parse_message_text_handles_rnn_resistance_operation_format(self) -> None:
        parsed = parse_message_text("تم رصد عملية مقاومة في لبنان  المناطق المتأثرة: تلّة العويضة، العديسة")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "ground_incursion")
        self.assertEqual(parsed.candidate_locations, ["تلة العويضة", "العديسة"])

    def test_parse_rnn_channel_message_handles_drone_flight_format(self) -> None:
        parsed = parse_rnn_channel_message("تم رصد تحليق مسيّرة في لبنان  المناطق المتأثرة: شمع")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "drone_movement")
        self.assertEqual(parsed.candidate_locations, ["شمع"])

    def test_parse_rnn_channel_message_handles_fighter_flight_format(self) -> None:
        parsed = parse_rnn_channel_message("تم رصد تحليق مقاتلات حربية في لبنان  المناطق المتأثرة: راشيا الفخار")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "fighter_jet_movement")
        self.assertEqual(parsed.candidate_locations, ["راشيا الفخار"])

    def test_parse_rnn_channel_message_keeps_resistance_operation_locations(self) -> None:
        parsed = parse_rnn_channel_message("تم رصد عملية مقاومة في لبنان عمليات المقاومة ضد جنود الاحتلال  المناطق المتأثرة: شمع، القنطرة، دير سريان")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "ground_incursion")
        self.assertEqual(parsed.candidate_locations, ["شمع", "القنطرة", "دير سريان"])

    def test_parse_rnn_channel_message_ignores_rnn_clashes_header_as_location(self) -> None:
        parsed = parse_rnn_channel_message("تم رصد اشتباكات في لبنان\nتوغل قوات الاحتلال نحو شمع\n\nالمناطق المتأثرة: الناقورة، البياضة، شمع")

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.event_type.value, "ground_incursion")
        self.assertEqual(parsed.candidate_locations, ["الناقورة"])

    def test_match_locations_skips_generic_al_jiwar_location(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add_all(
                [
                    Location(name_ar="الجوار", latitude=33.9, longitude=35.7),
                    Location(name_ar="سير الغربية", governorate="Nabatîyé", latitude=33.4, longitude=35.5),
                ]
            )
            session.commit()

            matches = match_locations(session, ["الجوار", "سير الغربية"])

            self.assertEqual([match.location.name_ar for match in matches.matches], ["سير الغربية"])
            self.assertEqual(matches.unmatched, ["الجوار"])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_match_locations_resolves_amiad_base_alias(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add(
                Location(
                    name_ar="عميعاد",
                    name_en="Amiad Junction",
                    alt_names='["قاعدة عميعاد", "قاعدة_عميعاد", "Amiad Junction"]',
                    governorate="Northern District (Israel)",
                    latitude=32.9134269,
                    longitude=35.5435212,
                )
            )
            session.commit()

            matches = match_locations(session, ["قاعدة عميعاد"])

            self.assertEqual([match.location.name_ar for match in matches.matches], ["عميعاد"])
            self.assertEqual(matches.unmatched, [])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_match_locations_prefers_south_bayada_for_border_context(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add_all(
                [
                    Location(name_ar="البياضة", name_en="El Biyada", governorate="Béqaa", latitude=33.8175, longitude=35.83861),
                    Location(name_ar="البياضة", name_en="El Bayyada", governorate="Nabatîyé", latitude=33.36833, longitude=35.42861),
                ]
            )
            session.commit()

            matches = match_locations(session, ["البياضة"])

            self.assertEqual([match.location.governorate for match in matches.matches], ["Nabatîyé"])
            self.assertEqual(matches.unmatched, [])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_match_locations_prefers_israel_metula_and_margaliot_aliases(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add_all(
                [
                    Location(name_ar="المطلّة", governorate="Mont-Liban", latitude=33.8, longitude=35.6),
                    Location(
                        name_ar="المطلة",
                        name_en="Metula",
                        governorate="Northern District (Israel)",
                        latitude=33.2692138,
                        longitude=35.5723384,
                    ),
                    Location(
                        name_ar="مرجليوت",
                        name_en="Margaliot",
                        alt_names='["مرغليوت", "Margaliot"]',
                        governorate="Northern District (Israel)",
                        latitude=33.2148047,
                        longitude=35.5444859,
                    ),
                ]
            )
            session.commit()

            matches = match_locations(session, ["المطلة", "مرغليوت"])

            self.assertEqual([match.location.name_ar for match in matches.matches], ["المطلة", "مرجليوت"])
            self.assertEqual(matches.unmatched, [])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_match_locations_overrides_khanouq_to_israel_side(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add(
                Location(
                    name_ar="الخانوق",
                    name_en="El Khanouq",
                    governorate="Mont-Liban",
                    latitude=33.97333,
                    longitude=35.7125,
                )
            )
            session.commit()

            matches = match_locations(session, ["الخانوق"])

            self.assertEqual(len(matches.matches), 1)
            self.assertEqual(matches.matches[0].location.name_ar, "الخانوق")
            self.assertEqual(matches.matches[0].location.governorate, "Northern District (Israel)")
            self.assertEqual(matches.unmatched, [])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_match_locations_rewrites_yohmor_shqif_split_candidate(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add_all(
                [
                    Location(
                        name_ar="شقيف",
                        name_en="Chqaif",
                        governorate="Mont-Liban",
                        latitude=34.07139,
                        longitude=35.65417,
                    ),
                    Location(
                        name_ar="يحمر البقاع",
                        name_en="Yohmor el Beqaa",
                        governorate="Béqaa",
                        latitude=33.48528,
                        longitude=35.66889,
                    ),
                ]
            )
            session.commit()

            matches = match_locations(session, ["يحمر", "شقيف"])

            self.assertEqual([match.location.name_ar for match in matches.matches], ["يحمر الشقيف"])
            self.assertEqual(matches.matches[0].location.governorate, "Nabatieh")
            self.assertEqual(matches.unmatched, [])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)

    def test_match_locations_rewrites_bent_jbeil_split_candidate(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=engine)
        session = Session()

        try:
            session.add_all(
                [
                    Location(name_ar="جبيل", name_en="Byblos", governorate="Mont-Liban", latitude=34.12111, longitude=35.64806),
                    Location(name_ar="بنت جبيل", name_en="Bent Jbail", governorate="Nabatieh", latitude=33.11944, longitude=35.43333),
                ]
            )
            session.commit()

            matches = match_locations(session, ["بنت", "جبيل"])

            self.assertEqual([match.location.name_ar for match in matches.matches], ["بنت جبيل"])
            self.assertEqual(matches.unmatched, [])
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    unittest.main()
