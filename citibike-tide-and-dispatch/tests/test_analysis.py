import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


agg = module("aggregate", "build_agg_tables.py")
forecast = module("forecast_bike", "phase5_forecast.py")


class AnalysisChecks(unittest.TestCase):
    def test_return_uses_end_hour(self):
        frame = pd.DataFrame(
            {
                "start_time": pd.to_datetime(["2019-05-01 07:50"]),
                "end_time": pd.to_datetime(["2019-05-01 08:05"]),
                "start_station_id": [1],
                "end_station_id": [2],
            }
        )
        self.assertEqual(agg.event_counts(frame, "out").index[0][1], 7)
        self.assertEqual(agg.event_counts(frame, "in").index[0][1], 8)

    def test_forecast_has_no_current_weather_or_target(self):
        n = 200
        frame = pd.DataFrame(
            {
                "rides": np.arange(n),
                "temp_c": 20.0,
                "precip_mm": 0.0,
                "wind_kmh": 3.0,
                "hour": np.arange(n) % 24,
                "weekday": np.arange(n) // 24 % 7,
            }
        )
        before = forecast.make_features(frame)
        frame.loc[180:, ["rides", "temp_c", "precip_mm", "wind_kmh"]] = 9999
        pd.testing.assert_frame_equal(
            before.iloc[:181], forecast.make_features(frame).iloc[:181]
        )


if __name__ == "__main__":
    unittest.main()
