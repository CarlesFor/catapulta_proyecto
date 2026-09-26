"""Pruebas locales: el servidor simulado nunca contacta con la placa."""

from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_core import DeviceError, ESP32Client, calculate_shot, normalize_address


@contextmanager
def fake_device(payload, status=200, extra_headers=None, disconnect=False):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append((self.command, self.path, body, dict(self.headers)))
            if disconnect:
                self.close_connection = True
                return
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ShotTests(unittest.TestCase):
    def test_center_has_full_travel_and_edges_have_minimum(self):
        center = calculate_shot(0.5)
        self.assertEqual((center.factor, center.travel_degrees, center.target_degrees), (1.0, 120.0, 0.0))
        self.assertEqual(center.rating, "¡TIRO PERFECTO!")
        for position in (0, 1):
            edge = calculate_shot(position)
            self.assertEqual((edge.factor, edge.travel_degrees, edge.target_degrees), (0.1, 12.0, 108.0))
            self.assertEqual(edge.rating, "¡OTRA OPORTUNIDAD!")

    def test_outside_positions_are_clamped(self):
        self.assertEqual(calculate_shot(-5), calculate_shot(0))
        self.assertEqual(calculate_shot(8), calculate_shot(1))

    def test_non_finite_positions_are_rejected(self):
        for position in (float("nan"), float("inf"), -float("inf"), None, "not a number"):
            with self.subTest(position=position), self.assertRaises(ValueError):
                calculate_shot(position)

    def test_travel_is_symmetric_and_increases_toward_center(self):
        previous = 0.0
        for step in range(51):
            position = step / 100
            shot = calculate_shot(position)
            opposite = calculate_shot(1.0 - position)
            self.assertAlmostEqual(shot.factor, opposite.factor)
            self.assertAlmostEqual(shot.target_degrees, opposite.target_degrees)
            self.assertGreater(shot.travel_degrees, previous)
            self.assertAlmostEqual(shot.travel_degrees + shot.target_degrees, 120.0)
            previous = shot.travel_degrees

    def test_rating_bands(self):
        examples = (
            (0.49, "¡CASI PERFECTO!"),
            (0.40, "¡BUEN TIRO!"),
            (0.20, "PUEDES AFINAR MÁS"),
            (0.10, "¡OTRA OPORTUNIDAD!"),
        )
        for position, rating in examples:
            with self.subTest(position=position):
                self.assertEqual(calculate_shot(position).rating, rating)

    def test_captured_shot_is_immutable(self):
        shot = calculate_shot(0.5)
        with self.assertRaises(FrozenInstanceError):
            shot.factor = 0.1


class AddressTests(unittest.TestCase):
    def test_addresses_are_normalized(self):
        for source, expected in (
            (" 192.0.2.1 ", "http://192.0.2.1"),
            ("http://ESP32.local:8080/", "http://esp32.local:8080"),
            ("localhost:8000", "http://localhost:8000"),
            ("http://[::1]:8000/", "http://[::1]:8000"),
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_address(source), expected)

    def test_paths_credentials_queries_and_invalid_ports_are_rejected(self):
        for address in (
            "", "https://esp32.local", "http://esp32.local/estado", "http://esp32.local//",
            "http://user:password@esp32.local", "http://esp32.local?x=1", "http://esp32.local?",
            "http://esp32.local#", "http://esp32.local:70000", "http://esp32.local:0",
            "http://esp32.local:", "http://bad host", "http://bad\nhost", "http://host\\path",
        ):
            with self.subTest(address=address), self.assertRaises(DeviceError):
                normalize_address(address)


class ClientTests(unittest.TestCase):
    def test_status_uses_get_and_checks_version(self):
        response = {"api_version": 1, "estado": "listo", "last_shot_id": ""}
        with fake_device(response) as (address, requests):
            self.assertEqual(ESP32Client(address).get_status(), response)
            self.assertEqual(requests[0][:3], ("GET", "/estado", b""))

    def test_old_firmware_and_unknown_states_are_rejected(self):
        for response in (
            b"ESP32 conectado", {"estado": "listo"}, {"api_version": 2, "estado": "listo"},
            {"api_version": True, "estado": "listo"}, {"api_version": 1, "estado": "desconocido"},
        ):
            with self.subTest(response=response), fake_device(response) as (address, _):
                with self.assertRaises(DeviceError):
                    ESP32Client(address).get_status()

    def test_post_encodes_power_and_id_and_returns_acceptance(self):
        response = {
            "aceptado": True, "id": "shot-123_A", "potencia": 0.712346,
            "recorrido_grados": 85, "angulo_objetivo": 35, "duracion_ms": 1000,
        }
        with fake_device(response, 202) as (address, requests):
            self.assertEqual(ESP32Client(address).fire(0.7123456, "shot-123_A"), response)
            self.assertEqual(len(requests), 1)
            method, path, body, headers = requests[0]
            self.assertEqual((method, path), ("POST", "/disparar"))
            self.assertEqual(parse_qs(body.decode("ascii")), {"potencia": ["0.712346"], "id": ["shot-123_A"]})
            self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")

    def test_wrong_id_or_unaccepted_response_is_not_successful(self):
        for response, status in (
            ({"aceptado": True, "id": "other-shot"}, 202),
            ({"aceptado": False, "id": "shot"}, 202),
            ({"aceptado": 1, "id": "shot"}, 202),
            ({"aceptado": True, "id": "shot"}, 200),
        ):
            with self.subTest(response=response, status=status), fake_device(response, status) as (address, requests):
                with self.assertRaises(DeviceError):
                    ESP32Client(address).fire(0.5, "shot")
                self.assertEqual(len(requests), 1)

    def test_http_error_exposes_device_message_without_retry(self):
        with fake_device({"error": "Catapulta ocupada"}, 409) as (address, requests):
            with self.assertRaisesRegex(DeviceError, "409.*Catapulta ocupada"):
                ESP32Client(address).fire(0.5, "shot")
            self.assertEqual(len(requests), 1)

    def test_redirect_is_not_followed(self):
        with fake_device({}, 302, {"Location": "/otro-destino"}) as (address, requests):
            with self.assertRaisesRegex(DeviceError, "302"):
                ESP32Client(address).fire(0.5, "shot")
            self.assertEqual(len(requests), 1)

    def test_lost_response_reports_uncertainty_without_resending(self):
        with fake_device({}, disconnect=True) as (address, requests):
            with self.assertRaisesRegex(DeviceError, "la orden podría haber llegado"):
                ESP32Client(address).fire(0.5, "shot")
            self.assertEqual(len(requests), 1)

    def test_invalid_responses_are_reported_without_retry(self):
        for response in (b"{broken", b"\xff", [], None):
            with self.subTest(response=response), fake_device(response, 202) as (address, requests):
                with self.assertRaises(DeviceError):
                    ESP32Client(address).fire(0.5, "shot")
                self.assertEqual(len(requests), 1)

    def test_invalid_shot_is_rejected_before_any_request(self):
        with fake_device({}) as (address, requests):
            client = ESP32Client(address)
            for factor, shot_id in (
                (0.09, "shot"), (1.1, "shot"), (float("nan"), "shot"), (float("inf"), "shot"),
                (None, "shot"), (0.5, ""), (0.5, "a b"), (0.5, "x" * 65), (0.5, "ñ"),
            ):
                with self.subTest(factor=factor, shot_id=shot_id), self.assertRaises(DeviceError):
                    client.fire(factor, shot_id)
            self.assertEqual(requests, [])

    def test_timeout_configuration_must_be_positive_and_finite(self):
        for timeout in (0, -1, float("inf"), float("nan"), None):
            with self.subTest(timeout=timeout), self.assertRaises(DeviceError):
                ESP32Client("localhost", timeout=timeout)


if __name__ == "__main__":
    unittest.main()
