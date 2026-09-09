import importlib.util
from pathlib import Path
import sys
import unittest
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import modeling

spec = importlib.util.spec_from_file_location(
    "road_clean", ROOT / "scripts/01_clean.py"
)
clean = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clean)


class AnalysisChecks(unittest.TestCase):
    def test_official_weekday_codes(self):
        frame = pd.DataFrame(
            {
                "collision_severity": [3, 3, 3],
                "date": ["03/01/2021", "04/01/2021", "09/01/2021"],
                "time": ["08:00"] * 3,
                "day_of_week": [1, 2, 7],
            }
        )
        self.assertEqual(clean.clean_basics(frame).is_weekend.tolist(), [1, 0, 1])

    def test_unknown_lighting_is_not_unlit(self):
        frame = pd.DataFrame(
            {
                "light_conditions": [7],
                "weather_conditions": [1],
                "road_surface_conditions": [1],
                "road_type": [6],
                "hour": [8],
                "urban_or_rural_area": [1],
                "first_road_class": [3],
            }
        )
        self.assertEqual(clean.label_categorical(frame).light.iloc[0], "不明")

    def test_post_collision_counts_excluded(self):
        self.assertNotIn("number_of_vehicles", modeling.FEATURES)
        self.assertNotIn("number_of_casualties", modeling.FEATURES)


if __name__ == "__main__":
    unittest.main()
