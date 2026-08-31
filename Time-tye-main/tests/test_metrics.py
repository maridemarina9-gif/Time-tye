import unittest

from tracking.metrics import calculate_metrics, format_duration, format_pace


class MetricsTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(format_duration(3661), "01:01:01")
        self.assertEqual(format_pace(5.5), "5:30/km")

    def test_metrics_use_recorded_points(self):
        points = [
            {"latitude": 0, "longitude": 0, "timestamp": "1", "accuracy": 10, "speed": 2},
            {"latitude": 0, "longitude": 0.0089, "timestamp": "2", "accuracy": 10, "speed": 2},
            {"latitude": 0, "longitude": 0.0178, "timestamp": "3", "accuracy": 10, "speed": 2},
        ]
        metrics = calculate_metrics(points, 600)
        self.assertGreater(metrics["distance_km"], 1)
        self.assertEqual(metrics["duration_seconds"], 600)
        self.assertGreater(metrics["calories"], 0)


    def test_calculate_splits(self):
        from tracking.metrics import calculate_splits
        # ~1.8 km total distance with points <= 1km delta
        points = [
            {"latitude": 0, "longitude": 0, "timestamp": "2026-08-31T18:00:00Z", "accuracy": 10},
            {"latitude": 0, "longitude": 0.005, "timestamp": "2026-08-31T18:03:00Z", "accuracy": 10},
            {"latitude": 0, "longitude": 0.010, "timestamp": "2026-08-31T18:06:00Z", "accuracy": 10},
            {"latitude": 0, "longitude": 0.015, "timestamp": "2026-08-31T18:09:00Z", "accuracy": 10},
        ]
        splits = calculate_splits(points)
        self.assertGreaterEqual(len(splits), 1)
        self.assertEqual(splits[0]["km"], 1)
        self.assertIn("formatted_pace", splits[0])
        self.assertIn("formatted_time", splits[0])


if __name__ == "__main__":
    unittest.main()