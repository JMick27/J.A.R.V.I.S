import unittest
from types import SimpleNamespace

from jarvis import JarvisApp, run_packaged_hand_tracking_self_test


def point(x: float, y: float, z: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y, z=z)


class HandGestureGeometryTests(unittest.TestCase):
    def test_straight_finger_is_extended(self) -> None:
        points = [point(0.5, 0.9) for _ in range(21)]
        points[5] = point(0.5, 0.7)
        points[6] = point(0.5, 0.55)
        points[7] = point(0.5, 0.40)
        points[8] = point(0.5, 0.22)
        self.assertTrue(JarvisApp._finger_is_extended(points, 5, 6, 7, 8))

    def test_bent_finger_is_not_extended(self) -> None:
        points = [point(0.5, 0.9) for _ in range(21)]
        points[5] = point(0.5, 0.7)
        points[6] = point(0.5, 0.55)
        points[7] = point(0.63, 0.55)
        points[8] = point(0.63, 0.68)
        self.assertFalse(JarvisApp._finger_is_extended(points, 5, 6, 7, 8))

    def test_palm_scaled_distance_is_rotation_independent(self) -> None:
        horizontal = [point(0.0, 0.0), point(0.3, 0.0)]
        vertical = [point(0.0, 0.0), point(0.0, 0.3)]
        self.assertAlmostEqual(JarvisApp._hand_distance(horizontal, 0, 1), 0.3)
        self.assertAlmostEqual(JarvisApp._hand_distance(vertical, 0, 1), 0.3)

    def test_hand_landmarker_runtime_initializes(self) -> None:
        self.assertTrue(run_packaged_hand_tracking_self_test())

    def test_centered_finger_uses_pointing_direction(self) -> None:
        points = [point(0.5, 0.5) for _ in range(21)]
        points[6] = point(0.48, 0.58)
        points[8] = point(0.52, 0.48)
        projected_x, projected_y = JarvisApp._project_index_pointer(points)
        self.assertGreater(projected_x, points[8].x)
        self.assertLess(projected_y, points[8].y)

    def test_direct_center_point_maps_to_center(self) -> None:
        points = [point(0.5, 0.5) for _ in range(21)]
        points[6] = point(0.5, 0.5, 0.1)
        points[8] = point(0.5, 0.5, -0.1)
        projected_x, projected_y = JarvisApp._project_index_pointer(points)
        self.assertAlmostEqual(projected_x, 0.5)
        self.assertAlmostEqual(projected_y, 0.5)


if __name__ == "__main__":
    unittest.main()
