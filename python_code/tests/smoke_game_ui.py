"""Prueba visual voluntaria: solo usa el modo práctica y un ESP32 simulado."""

from pathlib import Path
import sys
import time
import tkinter as tk
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_catapulta import CatapultGame, configure_display


def main():
    artifact_dir = Path(__file__).resolve().parents[2] / ".build"
    artifact_dir.mkdir(exist_ok=True)
    configure_display()
    root = tk.Tk()
    game = CatapultGame(root, practice=True)
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)

    def pump(seconds=0.15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update()
            time.sleep(0.01)

    try:
        pump()
        game.arena.focus_force()
        game.round.started_at = time.perf_counter() - game.round.crossing_seconds * 0.5
        with patch("app_catapulta.ESP32Client") as client_constructor:
            game._space_press()
            frozen_shot = game.round.shot
            assert frozen_shot is not None and frozen_shot.factor > 0.99
            assert game.phase == "result" and game.attempts == 1
            for _ in range(20):
                game._space_press()
            assert game.attempts == 1 and game.round.shot is frozen_shot
            client_constructor.assert_not_called()
        pump()

        # La captura solo contiene la ventana de este juego.
        try:
            from PIL import ImageGrab

            root.lift()
            pump()
            x, y = root.winfo_rootx(), root.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(
                artifact_dir / "game-preview.png"
            )
            print("Captura: .build/game-preview.png")
        except ImportError:
            print("Pillow no instalado: prueba visual sin captura.")

        game._space_release()
        game._space_press()
        assert game.phase == "moving" and game.attempts == 1
        game._space_release()
        pump()

        # Simula envío aceptado y retorno, sin usar ninguna dirección de red.
        fake = Mock()
        fake.fire.side_effect = lambda factor, shot_id: {"aceptado": True, "id": shot_id}
        fake.get_status.side_effect = lambda: {
            "api_version": 1, "estado": "listo", "last_shot_id": fake.fire.call_args.args[1]
        }
        game.practice.set(False)
        game.connected = True
        game.device_client = fake
        game._change_mode()
        game._space_press()
        assert game.phase == "sending"
        for _ in range(10):
            game.on_action()
        deadline = time.monotonic() + 4
        while game.network_busy and time.monotonic() < deadline:
            pump(0.05)
        assert game.phase == "result" and not game.network_busy
        assert game.attempts == 2 and fake.fire.call_count == 1
        game.address.set("192.0.2.2")
        assert not game.connected and game.device_client is None

        # Controles esenciales visibles también en el tamaño mínimo.
        root.geometry("900x740")
        pump()
        for widget in (game.arena, game.action_button, game.practice_check, game.network_label):
            assert widget.winfo_ismapped(), str(widget)
            assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height(), str(widget)
        for item in game.arena.find_all():
            if game.arena.type(item) == "text":
                assert game.arena.bbox(item)[3] <= game.arena.winfo_height(), game.arena.itemcget(item, "text")
        assert not errors, errors
        print("PASS: ventana, práctica, tecla sostenida, nueva ronda, hilo de envío, cambio de IP y tamaño mínimo.")
    finally:
        game.close()


if __name__ == "__main__":
    main()
