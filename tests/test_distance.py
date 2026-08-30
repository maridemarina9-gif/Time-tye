import unittest

from tracking.distance import filter_gps_points, haversine_km, route_distance_km


class DistanceTests(unittest.TestCase):
    def test_haversine_returns_zero_for_same_point(self):
        self.assertEqual(haversine_km(-23.55, -46.63, -23.55, -46.63), 0)

    def test_route_distance_sums_segments(self):
        points = [
            {"latitude": 0, "longitude": 0, "timestamp": "1", "accuracy": 10},
            {"latitude": 0, "longitude": 0.01, "timestamp": "2", "accuracy": 10},
            {"latitude": 0, "longitude": 0.02, "timestamp": "3", "accuracy": 10},
        ]
        self.assertAlmostEqual(route_distance_km(points), 2.224, places=2)

    def test_invalid_and_imprecise_points_are_removed(self):
        points = [
            {"latitude": 95, "longitude": 0, "timestamp": "1", "accuracy": 10},
            {"latitude": 0, "longitude": 0, "timestamp": "2", "accuracy": 120},
            {"latitude": 0, "longitude": 0, "timestamp": "3", "accuracy": 10},
        ]
        self.assertEqual(len(filter_gps_points(points)), 1)


if __name__ == "__main__":
    unittest.main()