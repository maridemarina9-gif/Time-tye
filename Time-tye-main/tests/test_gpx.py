import unittest

from tracking.gpx import generate_gpx


class GPXTests(unittest.TestCase):
    def test_generate_gpx_valid_xml(self):
        points = [
            {
                "latitude": -23.55052,
                "longitude": -46.633308,
                "altitude": 760.5,
                "speed": 3.2,
                "timestamp": "2026-08-31T18:00:00Z",
            },
            {
                "latitude": -23.55100,
                "longitude": -46.63400,
                "altitude": 762.0,
                "speed": 3.4,
                "timestamp": "2026-08-31T18:01:00Z",
            },
        ]
        xml = generate_gpx(points, track_name="Treino de Teste")
        self.assertTrue(xml.startswith("<?xml version="))
        self.assertIn('<gpx version="1.1"', xml)
        self.assertIn("<name>Treino de Teste</name>", xml)
        self.assertIn('<trkpt lat="-23.5505200" lon="-46.6333080">', xml)
        self.assertIn("<ele>760.5</ele>", xml)
        self.assertIn("<speed>3.20</speed>", xml)
        self.assertIn("</gpx>", xml)

    def test_generate_gpx_empty_points(self):
        xml = generate_gpx([])
        self.assertIn("<trkseg>", xml)
        self.assertIn("</trkseg>", xml)


if __name__ == "__main__":
    unittest.main()
