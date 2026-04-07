from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.ocr_service import detect_attack_side_from_image_bytes


def _build_labeled_image(label_rgb: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (320, 180), (248, 248, 248))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 320, 38), fill=label_rgb)
    draw.rectangle((20, 54, 300, 160), fill=(225, 232, 244))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class MediaLabelColorTests(unittest.TestCase):
    def test_red_label_maps_to_enemy_attack(self) -> None:
        label_color, attack_side = detect_attack_side_from_image_bytes(_build_labeled_image((220, 42, 66)))

        self.assertEqual(label_color, "red")
        self.assertEqual(attack_side, "enemy_attack")

    def test_purple_label_maps_to_resistance_attack(self) -> None:
        label_color, attack_side = detect_attack_side_from_image_bytes(_build_labeled_image((132, 72, 198)))

        self.assertEqual(label_color, "purple")
        self.assertEqual(attack_side, "resistance_attack")

    def test_orange_label_maps_to_enemy_attack(self) -> None:
        label_color, attack_side = detect_attack_side_from_image_bytes(_build_labeled_image((177, 91, 14)))

        self.assertEqual(label_color, "orange")
        self.assertEqual(attack_side, "enemy_attack")

    def test_green_label_maps_to_incursion_hint(self) -> None:
        label_color, attack_side = detect_attack_side_from_image_bytes(_build_labeled_image((54, 168, 92)))

        self.assertEqual(label_color, "green")
        self.assertIsNone(attack_side)

    def test_dark_green_label_maps_to_incursion_hint(self) -> None:
        label_color, attack_side = detect_attack_side_from_image_bytes(_build_labeled_image((86, 98, 24)))

        self.assertEqual(label_color, "green")
        self.assertIsNone(attack_side)

    def test_neutral_label_does_not_map_to_attack_side(self) -> None:
        label_color, attack_side = detect_attack_side_from_image_bytes(_build_labeled_image((105, 126, 156)))

        self.assertIsNone(label_color)
        self.assertIsNone(attack_side)


if __name__ == "__main__":
    unittest.main()
