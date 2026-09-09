import unittest
import numpy as np
import pandas as pd
from src.inventory import simulate
from src.forecast import features


class CoreChecks(unittest.TestCase):
    def group(self, demand, prediction):
        return pd.DataFrame(
            {
                "week": pd.date_range("2020-01-06", periods=len(demand), freq="W-MON"),
                "product_id": "A",
                "actual": demand,
                "prediction": prediction,
                "sigma": 0,
            }
        )

    def test_inventory_conservation(self):
        for lead in [0, 1]:
            g = simulate(self.group([3, 20, 0, 5], [10, 10, 10, 10]), 1, lead)
            np.testing.assert_allclose(g.opening + g.arrivals - g.fulfilled, g.ending)
            np.testing.assert_allclose(g.fulfilled + g.shortage, g.actual)
            self.assertTrue((g[["ending", "shortage", "order"]] >= 0).all().all())

    def test_known_zero_lead(self):
        g = simulate(self.group([3, 20], [10, 10]), 0, 0)
        self.assertEqual(g.ending.tolist(), [7, 0])
        self.assertEqual(g.order.tolist(), [10, 3])
        self.assertEqual(g.shortage.tolist(), [0, 10])

    def test_arrival_delay(self):
        g = simulate(self.group([5, 5, 5], [5, 5, 5]), 0, 1)
        self.assertEqual(g.arrivals.tolist(), [0, 10, 0])
        self.assertEqual(g.shortage.tolist(), [5, 0, 0])

    def test_features_do_not_see_present_or_future(self):
        y = pd.Series(np.arange(30, dtype=float))
        before = features(y)
        y.iloc[20:] = 99999
        pd.testing.assert_frame_equal(before.iloc[:21], features(y).iloc[:21])

    def test_simulation_does_not_see_future_demand(self):
        g = self.group([5, 6, 7], [5, 5, 5])
        before = simulate(g, 1, 1)
        g.loc[2, "actual"] = 1000
        pd.testing.assert_frame_equal(before.iloc[:2], simulate(g, 1, 1).iloc[:2])


if __name__ == "__main__":
    unittest.main()
