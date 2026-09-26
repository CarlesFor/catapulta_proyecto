"""Lógica del juego sin crear ventanas ni contactar con el ESP32."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_catapulta import CatapultGame, TimingRound, bar_color, tk
from game_core import DeviceError, calculate_shot


class BarColorTests(unittest.TestCase):
    def test_gradient_produces_valid_rgb_colors_across_the_bar(self):
        for step in range(101):
            with self.subTest(position=step / 100):
                self.assertRegex(bar_color(step / 100), r"^#[0-9a-f]{6}$")

    def test_gradient_is_symmetric_with_green_center_and_red_edges(self):
        self.assertEqual(bar_color(0.5), "#64efae")
        self.assertEqual(bar_color(0), "#f35a6b")
        self.assertEqual(bar_color(1), "#f35a6b")
        for step in range(65):
            position = step / 64
            with self.subTest(position=position):
                self.assertEqual(bar_color(position), bar_color(1 - position))


class TimingRoundTests(unittest.TestCase):
    def test_marker_crosses_and_bounces_at_both_edges(self):
        game_round = TimingRound(crossing_seconds=2)
        game_round.start(100)
        for elapsed, expected in (
            (0, 0), (1, 0.5), (2, 1), (3, 0.5), (4, 0),
            (4.5, 0.25), (5.5, 0.75), (6, 1), (7.5, 0.25),
        ):
            with self.subTest(elapsed=elapsed):
                self.assertAlmostEqual(game_round.position(100 + elapsed), expected)

    def test_elapsed_time_before_start_is_clamped(self):
        game_round = TimingRound()
        game_round.start(100)
        self.assertEqual(game_round.position(99), 0)

    def test_long_pause_keeps_position_in_range(self):
        game_round = TimingRound(crossing_seconds=2)
        game_round.start(0)
        self.assertEqual(game_round.position(1_000_000_003), 0.5)

    def test_stop_freezes_position_and_score(self):
        game_round = TimingRound(crossing_seconds=2)
        game_round.start(100)
        shot = game_round.stop(101)
        self.assertEqual(shot, calculate_shot(0.5))
        self.assertFalse(game_round.running)
        self.assertEqual(game_round.position(200), 0.5)
        self.assertIs(game_round.shot, shot)

    def test_repeated_stop_does_not_capture_another_shot(self):
        game_round = TimingRound(crossing_seconds=2)
        game_round.start(0)
        first_shot = game_round.stop(0.5)
        self.assertIsNone(game_round.stop(1.0))
        self.assertIs(game_round.shot, first_shot)

    def test_stop_before_start_has_no_result(self):
        self.assertIsNone(TimingRound().stop(10))

    def test_new_round_discards_frozen_result(self):
        game_round = TimingRound(crossing_seconds=2)
        game_round.start(0)
        game_round.stop(1)
        game_round.start(100)
        self.assertIsNone(game_round.shot)
        self.assertTrue(game_round.running)
        self.assertEqual(game_round.position(100), 0)
        self.assertEqual(game_round.stop(102), calculate_shot(1))

    def test_crossing_duration_must_be_positive_and_finite(self):
        for seconds in (0, -1, float("inf"), float("nan")):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                TimingRound(seconds)


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        self.game = object.__new__(CatapultGame)
        self.game.root = Mock()
        self.game.root.focus_get.return_value = None
        self.game.space_down = False
        self.game.on_action = Mock()

    def test_held_space_key_does_not_repeat_action(self):
        for _ in range(20):
            self.assertEqual(self.game._space_press(), "break")
        self.game.on_action.assert_called_once_with()

    def test_release_allows_one_new_action(self):
        self.game._space_press()
        self.game._space_press()
        self.game._space_release()
        self.game._space_press()
        self.assertEqual(self.game.on_action.call_count, 2)

    def test_space_in_ip_entry_does_not_trigger_a_shot(self):
        self.game.root.focus_get.return_value = Mock(spec=tk.Entry)
        self.assertIsNone(self.game._space_press())
        self.assertIsNone(self.game._space_release())
        self.game.on_action.assert_not_called()
        self.assertFalse(self.game.space_down)

    def test_losing_window_focus_releases_space_latch(self):
        self.game._space_press()
        self.game._focus_out(Mock(widget=self.game.root))
        self.game._space_press()
        self.assertEqual(self.game.on_action.call_count, 2)


class FireSequenceTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.shot = calculate_shot(0.5)
        self.shot_id = "single-shot"
        self.acknowledgement = {"aceptado": True, "id": self.shot_id}
        self.client.fire.return_value = self.acknowledgement
        self.sleep_patcher = patch("app_catapulta.time.sleep")
        self.sleep = self.sleep_patcher.start()
        self.addCleanup(self.sleep_patcher.stop)

    def status(self, state="listo", shot_id=None):
        return {"estado": state, "last_shot_id": self.shot_id if shot_id is None else shot_id}

    def test_one_order_then_confirmation(self):
        self.client.get_status.return_value = self.status()
        result = CatapultGame._fire_and_wait(self.client, self.shot, self.shot_id)
        self.assertIs(result, self.acknowledgement)
        self.assertEqual(self.client.method_calls, [
            call.fire(1.0, self.shot_id), call.get_status(),
        ])
        self.sleep.assert_called_once_with(1.05)

    def test_busy_status_only_repeats_queries_not_the_order(self):
        self.client.get_status.side_effect = [self.status("disparando"), self.status()]
        with patch("app_catapulta.time.monotonic", return_value=0):
            CatapultGame._fire_and_wait(self.client, self.shot, self.shot_id)
        self.client.fire.assert_called_once_with(1.0, self.shot_id)
        self.assertEqual(self.client.get_status.call_count, 2)
        self.assertEqual(self.sleep.call_args_list, [call(1.05), call(0.15)])

    def test_failed_order_is_not_retried_or_followed_by_queries(self):
        self.client.fire.side_effect = DeviceError("No se pudo confirmar el tiro")
        with self.assertRaisesRegex(DeviceError, "No se pudo confirmar"):
            CatapultGame._fire_and_wait(self.client, self.shot, self.shot_id)
        self.client.fire.assert_called_once_with(1.0, self.shot_id)
        self.client.get_status.assert_not_called()
        self.sleep.assert_not_called()

    def test_failed_confirmation_never_resends_order(self):
        self.client.get_status.side_effect = DeviceError("Sin respuesta")
        with self.assertRaisesRegex(DeviceError, "Sin respuesta"):
            CatapultGame._fire_and_wait(self.client, self.shot, self.shot_id)
        self.client.fire.assert_called_once_with(1.0, self.shot_id)
        self.client.get_status.assert_called_once_with()

    def test_another_shot_is_not_reported_as_success(self):
        self.client.get_status.return_value = self.status(shot_id="another-shot")
        with self.assertRaisesRegex(DeviceError, "otro tiro"):
            CatapultGame._fire_and_wait(self.client, self.shot, self.shot_id)
        self.client.fire.assert_called_once_with(1.0, self.shot_id)

    def test_return_timeout_never_resends_order(self):
        self.client.get_status.return_value = self.status("disparando")
        with patch("app_catapulta.time.monotonic", side_effect=[10, 10.5, 13]):
            with self.assertRaisesRegex(DeviceError, "no se confirmó el retorno"):
                CatapultGame._fire_and_wait(self.client, self.shot, self.shot_id)
        self.client.fire.assert_called_once_with(1.0, self.shot_id)
        self.assertEqual(self.client.get_status.call_count, 2)


if __name__ == "__main__":
    unittest.main()
