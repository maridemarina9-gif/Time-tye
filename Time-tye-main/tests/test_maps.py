import unittest

from maps.map import _calculate_view_state, _safe_public_point


class MapTests(unittest.TestCase):
    def test_safe_public_point_exact(self):
        lat, lon = _safe_public_point(-23.55052, -46.633308, "exact")
        self.assertEqual(lat, -23.55052)
        self.assertEqual(lon, -46.633308)

    def test_safe_public_point_approximate(self):
        lat, lon = _safe_public_point(-23.55052, -46.633308, "approximate")
        self.assertEqual(lat, -23.551)
        self.assertEqual(lon, -46.633)

    def test_calculate_view_state_single_point(self):
        rows = [{"latitude": -23.55, "longitude": -46.63}]
        view_state = _calculate_view_state(rows)
        self.assertEqual(view_state.latitude, -23.55)
        self.assertEqual(view_state.longitude, -46.63)
        self.assertEqual(view_state.zoom, 16)

    def test_render_route_map_handles_empty_and_single_point(self):
        from maps.map import render_route_map
        # Should not raise any exceptions
        render_route_map([])
        render_route_map([{"latitude": -23.55, "longitude": -46.63}])
        render_route_map([{"latitude": None, "longitude": -46.63}])
        render_route_map([
            {"latitude": -23.55, "longitude": -46.63},
            {"latitude": -23.56, "longitude": -46.64},
        ])

    def test_render_live_map_handles_empty_and_valid_locations(self):
        from maps.map import render_live_map
        # Should not raise any exceptions
        render_live_map([])
        render_live_map([
            {"name": "Runner 1", "latitude": -23.55, "longitude": -46.63, "distance": 5.2, "pace": 5.5, "status": "running"}
        ])
        render_live_map([
            {"name": "Invalid", "latitude": None, "longitude": None}
        ])


if __name__ == "__main__":
    unittest.main()

