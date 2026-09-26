"""Minijuego de precisión. Ejecutar con --demo para jugar sin la placa."""

from __future__ import annotations

import argparse
import math
import queue
import sys
import threading
import time
import tkinter as tk
import uuid
from typing import Callable

from game_core import DeviceError, ESP32Client, Shot, calculate_shot


BACKGROUND = "#0b1115"
PANEL = "#141f25"
LINE = "#2a3b43"
WHITE = "#edf5f4"
MUTED = "#92a7af"
GREEN = "#64efae"
RED = "#f36a77"
YELLOW = "#f6cd66"
DEFAULT_ADDRESS = "192.0.2.1"


def configure_display():
    """Evita que Windows amplíe y recorte la ventana en pantallas con escala."""
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


class TimingRound:
    """El tiempo real determina el marcador, independientemente de los FPS."""

    def __init__(self, crossing_seconds: float = 1.65):
        if not math.isfinite(crossing_seconds) or crossing_seconds <= 0:
            raise ValueError("La duración del recorrido debe ser positiva.")
        self.crossing_seconds = crossing_seconds
        self.started_at = 0.0
        self.running = False
        self.shot: Shot | None = None

    def start(self, now: float) -> None:
        self.started_at = now
        self.running = True
        self.shot = None

    def position(self, now: float) -> float:
        if self.shot is not None:
            return self.shot.position
        phase = (max(0.0, now - self.started_at) / self.crossing_seconds) % 2.0
        return phase if phase <= 1.0 else 2.0 - phase

    def stop(self, now: float) -> Shot | None:
        if not self.running:
            return None
        self.shot = calculate_shot(self.position(now))
        self.running = False
        return self.shot


def bar_color(position: float) -> str:
    precision = 1.0 - abs(2.0 * position - 1.0)
    stops = ((243, 90, 107), (246, 205, 102), (100, 239, 174))
    first, second = (stops[0], stops[1]) if precision <= 0.5 else (stops[1], stops[2])
    amount = precision * 2.0 if precision <= 0.5 else (precision - 0.5) * 2.0
    rgb = tuple(round(a + (b - a) * amount) for a, b in zip(first, second))
    return "#%02x%02x%02x" % rgb


class CatapultGame:
    def __init__(self, root: tk.Tk, address: str = DEFAULT_ADDRESS, practice: bool = False):
        self.root = root
        self.root.title("Catapulta · Clava el centro")
        self.root.geometry("1040x780")
        self.root.minsize(900, 740)
        self.root.configure(bg=BACKGROUND)
        self.root.option_add("*Font", ("Segoe UI", 10))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.events: queue.Queue = queue.Queue()
        self.closed = False
        self.network_busy = False
        self.connected = False
        self.device_client: ESP32Client | None = None
        self.space_down = False
        self.phase = "moving"
        self.round = TimingRound()
        self.round.start(time.perf_counter())
        self.attempts = 0
        self.best = 0.0
        self.history: list[Shot] = []
        self.practice = tk.BooleanVar(value=practice)
        self.address = tk.StringVar(value=address)
        self.bar_bounds = (42.0, 94.0, 850.0, 62.0)
        self.marker_items: list[int] = []
        self.frame_job = None
        self.poll_job = None
        self.connect_job = None
        self._build_ui()
        self.address.trace_add("write", self._address_changed)
        self.root.bind("<KeyPress-space>", self._space_press)
        self.root.bind("<KeyRelease-space>", self._space_release)
        self.root.bind("<FocusOut>", self._focus_out)
        self.arena.bind("<Button-1>", lambda _event: self.arena.focus_set())
        self._refresh_controls()
        self._animate()
        self._poll_events()
        if practice:
            self.connection_label.config(text="●  PRÁCTICA", fg=YELLOW)
            self.network_label.config(text="Juega sin enviar órdenes a la catapulta.")
        else:
            self.connect_job = self.root.after(300, self.connect_device)

    def _label(self, parent, text, size=11, color=WHITE, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BACKGROUND)
        outer.pack(fill="both", expand=True, padx=36, pady=(25, 20))
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(3, weight=1)
        top = tk.Frame(outer, bg=BACKGROUND)
        top.grid(row=0, column=0, sticky="ew")
        self._label(top, "◈  CATAPULTA  /  ARCADE", 11, GREEN, True).pack(side="left")
        self.round_label = self._label(top, "RONDA 01", 10, MUTED, True)
        self.round_label.pack(side="right")

        self._label(outer, "Clava el centro.", 37, WHITE, True).grid(row=1, column=0, sticky="w", pady=(12, 0))
        self._label(outer, "Detén el marcador con ESPACIO. Cuanto más cerca del verde, mejor el tiro.",
                    12, MUTED).grid(row=2, column=0, sticky="w", pady=(3, 16))

        self.arena = tk.Canvas(outer, height=240, bg=PANEL, highlightthickness=1,
                               highlightbackground=LINE, takefocus=True)
        self.arena.grid(row=3, column=0, sticky="nsew")
        self.arena.bind("<Configure>", self._draw_arena)

        metrics = tk.Frame(outer, bg=BACKGROUND)
        metrics.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        for column in range(3):
            metrics.grid_columnconfigure(column, weight=1, uniform="metrics")
        self.power_label, self.factor_label = self._metric(metrics, 0, "POTENCIA DEL TIRO", "10,0 %", "× 0,100")
        self.travel_label, _ = self._metric(metrics, 1, "RECORRIDO DEL SERVO", "12,0°", "Máximo 120° · retorno en 1 s")
        self.best_label, self.history_label = self._metric(metrics, 2, "TU MEJOR TIRO", "—", "Tu primera ronda te espera")

        result = tk.Frame(outer, bg=BACKGROUND)
        result.grid(row=5, column=0, sticky="ew", pady=(17, 12))
        text = tk.Frame(result, bg=BACKGROUND)
        self.result_label = self._label(text, "Todo está en el momento.", 17, WHITE, True)
        self.result_label.pack(anchor="w")
        self.detail_label = self._label(text, "El marcador rebota. Tú eliges cuándo parar.", 10, MUTED)
        self.detail_label.pack(anchor="w", pady=(4, 0))
        self.action_button = tk.Button(result, text="DETENER  ·  ESPACIO", command=self.on_action,
                                      bg=GREEN, fg=BACKGROUND, activebackground="#8fffc8",
                                      activeforeground=BACKGROUND, relief="flat", borderwidth=0,
                                      font=("Segoe UI", 11, "bold"), padx=20, pady=14,
                                      cursor="hand2", takefocus=False, disabledforeground=MUTED)
        self.action_button.pack(side="right", padx=(12, 0))
        text.pack(side="left", fill="x", expand=True)

        connection = tk.Frame(outer, bg=PANEL, padx=16, pady=12,
                              highlightthickness=1, highlightbackground=LINE)
        connection.grid(row=6, column=0, sticky="ew")
        controls = tk.Frame(connection, bg=PANEL)
        controls.pack(fill="x")
        self.connection_label = self._label(controls, "●  SIN CONECTAR", 10, MUTED, True)
        self.connection_label.pack(side="left", padx=(0, 18))
        self._label(controls, "IP", 10, MUTED).pack(side="left", padx=(0, 6))
        self.ip_entry = tk.Entry(controls, textvariable=self.address, width=19, bg=BACKGROUND,
                                 fg=WHITE, insertbackground=GREEN, relief="flat",
                                 disabledbackground=BACKGROUND, disabledforeground=MUTED,
                                 font=("Consolas", 11), highlightthickness=1,
                                 highlightbackground=LINE, highlightcolor=GREEN)
        self.ip_entry.pack(side="left", ipady=5)
        self.ip_entry.bind("<Return>", lambda _event: self.connect_device())
        self.connect_button = tk.Button(controls, text="Conectar", command=self.connect_device,
                                       bg=LINE, fg=WHITE, activebackground="#3b535d",
                                       activeforeground=WHITE, relief="flat", padx=14, pady=5,
                                       cursor="hand2", takefocus=False)
        self.connect_button.pack(side="left", padx=8)
        self.practice_check = tk.Checkbutton(controls, text="Práctica · sin catapulta",
                                            variable=self.practice, command=self._change_mode,
                                            bg=PANEL, fg=MUTED, selectcolor=BACKGROUND,
                                            activebackground=PANEL, activeforeground=WHITE,
                                            highlightthickness=0, takefocus=False, cursor="hand2")
        self.practice_check.pack(side="right")
        self.network_label = self._label(connection, "Comprobando la conexión con el ESP32…", 10, MUTED,
                                         anchor="w", justify="left", wraplength=850)
        self.network_label.pack(fill="x", pady=(8, 0))
        outer.bind("<Configure>", self._resize_text)

    def _resize_text(self, event):
        self.network_label.config(wraplength=max(300, event.width - 36))
        self.detail_label.config(wraplength=max(250, event.width - 340))

    def _metric(self, parent, column, title, value, caption):
        card = tk.Frame(parent, bg=PANEL, padx=17, pady=12)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 12, 0))
        self._label(card, title, 9, MUTED, True).pack(anchor="w")
        number = self._label(card, value, 27, GREEN if column == 0 else WHITE, True)
        number.pack(anchor="w", pady=(2, 0))
        note = self._label(card, caption, 9, MUTED)
        note.pack(anchor="w")
        return number, note

    def _draw_arena(self, event=None):
        canvas = self.arena
        canvas.delete("all")
        width = max(200, canvas.winfo_width())
        height = max(100, canvas.winfo_height())
        compact = height < 190
        bar_height = 42.0 if compact else 62.0
        x, y, bar_width = 42.0, max(48, min(height * 0.40, height - bar_height - 45)), width - 84.0
        self.bar_bounds = (x, y, bar_width, bar_height)
        center = x + bar_width / 2
        canvas.create_text(x, 20 if compact else 28, anchor="w", text="ENCUENTRA TU MOMENTO", fill=MUTED,
                           font=("Segoe UI", 9, "bold"))
        canvas.create_text(width - 42, 20 if compact else 28, anchor="e", text="PRECISIÓN = POTENCIA", fill=MUTED,
                           font=("Segoe UI", 9))
        canvas.create_rectangle(center - 58, y - 41, center + 58, y - 19, fill="#203e35", outline="")
        canvas.create_text(center, y - 30, text="TIRO PERFECTO", fill=GREEN,
                           font=("Segoe UI", 8, "bold"))
        canvas.create_rectangle(x - 5, y - 5, x + bar_width + 5, y + bar_height + 5,
                                fill=BACKGROUND, outline=LINE)
        segments = max(2, int(bar_width / 2))
        for i in range(segments):
            canvas.create_rectangle(x + bar_width * i / segments, y,
                                    x + bar_width * (i + 1) / segments + 1, y + bar_height,
                                    fill=bar_color(i / (segments - 1)), outline="")
        canvas.create_line(x, y + 2, x + bar_width, y + 2, fill="#ffffff", stipple="gray75")
        for tick in range(21):
            tx = x + bar_width * tick / 20
            canvas.create_line(tx, y + bar_height + 12, tx,
                               y + bar_height + (21 if tick % 5 == 0 else 17), fill=LINE)
        canvas.create_line(center, y - 12, center, y + bar_height + 24, fill=WHITE, dash=(3, 5))
        for position, text, color in ((0, "10 %", RED), (0.5, "100 %", GREEN), (1, "10 %", RED)):
            canvas.create_text(x + bar_width * position, y + bar_height + (30 if compact else 38),
                               text=text, fill=color, font=("Segoe UI", 9 if compact else 10, "bold"))
        shadow = canvas.create_rectangle(0, 0, 0, 0, fill=BACKGROUND, outline="")
        marker = canvas.create_rectangle(0, 0, 0, 0, fill=WHITE, outline=WHITE)
        top = canvas.create_polygon(0, 0, 0, 0, 0, 0, fill=WHITE, outline="")
        bottom = canvas.create_polygon(0, 0, 0, 0, 0, 0, fill=WHITE, outline="")
        self.marker_items = [shadow, marker, top, bottom]
        self._position_marker(self.round.position(time.perf_counter()))

    def _position_marker(self, position):
        if not self.marker_items:
            return
        x, y, width, height = self.bar_bounds
        mx = x + width * position
        shadow, marker, top, bottom = self.marker_items
        self.arena.coords(shadow, mx - 7, y - 5, mx + 7, y + height + 5)
        self.arena.coords(marker, mx - 3, y - 4, mx + 3, y + height + 4)
        self.arena.coords(top, mx - 9, y - 17, mx + 9, y - 17, mx, y - 7)
        self.arena.coords(bottom, mx - 9, y + height + 17, mx + 9, y + height + 17,
                          mx, y + height + 7)

    @staticmethod
    def _decimal(value, digits=1):
        return f"{value:.{digits}f}".replace(".", ",")

    def _show_shot(self, shot):
        self._position_marker(shot.position)
        self.power_label.config(text=f"{self._decimal(shot.factor * 100)} %", fg=bar_color(shot.position))
        self.factor_label.config(text=f"× {self._decimal(shot.factor, 3)}")
        self.travel_label.config(text=f"{self._decimal(shot.travel_degrees)}°")

    def _animate(self):
        if self.closed:
            return
        if self.phase == "moving":
            self._show_shot(calculate_shot(self.round.position(time.perf_counter())))
        self.frame_job = self.root.after(16, self._animate)

    def _space_press(self, _event=None):
        if isinstance(self.root.focus_get(), tk.Entry):
            return None
        if not self.space_down:
            self.space_down = True
            self.on_action()
        return "break"

    def _space_release(self, _event=None):
        self.space_down = False
        return None if isinstance(self.root.focus_get(), tk.Entry) else "break"

    def _focus_out(self, event):
        if event.widget is self.root:
            self.space_down = False

    def on_action(self):
        if self.closed or self.network_busy:
            return
        self.arena.focus_set()
        if self.phase == "result":
            self.round.start(time.perf_counter())
            self.phase = "moving"
            self.round_label.config(text=f"RONDA {self.attempts + 1:02d}")
            self.result_label.config(text="Otra oportunidad de clavarlo.", fg=WHITE)
            self.detail_label.config(text="Detén el marcador en el centro con ESPACIO.")
            self._refresh_controls()
            return
        if self.phase != "moving":
            return
        shot = self.round.stop(time.perf_counter())
        if shot is None:
            return
        self._show_shot(shot)
        self.attempts += 1
        self.best = max(self.best, shot.factor)
        self.history.append(shot)
        self.best_label.config(text=f"{self._decimal(self.best * 100)} %")
        self.history_label.config(text="Últimos: " + " · ".join(f"{s.factor * 100:.0f}%" for s in self.history[-4:]))
        self.result_label.config(text=shot.rating, fg=bar_color(shot.position))
        self.phase = "result"
        if self.practice.get():
            self.detail_label.config(text="Práctica completada. ESPACIO para otra ronda.")
        elif not self.connected or self.device_client is None:
            self.detail_label.config(text="Resultado guardado. Conecta el ESP32 para enviar tiros.")
            self.network_label.config(text="No se ha enviado ninguna orden. Conecta la placa o activa Práctica.")
        else:
            self.phase = "sending"
            self.detail_label.config(text="Enviando el tiro y esperando el retorno del servo…")
            client, shot_id = self.device_client, uuid.uuid4().hex
            self._begin_task("shot", lambda: self._fire_and_wait(client, shot, shot_id))
        self._refresh_controls()

    @staticmethod
    def _fire_and_wait(client, shot, shot_id):
        acknowledgement = client.fire(shot.factor, shot_id)
        # El ESP32 hace el retorno. La app únicamente consulta su estado.
        time.sleep(1.05)
        deadline = time.monotonic() + 3.0
        while True:
            status = client.get_status()
            if status.get("last_shot_id") != shot_id:
                raise DeviceError("La placa respondió con otro tiro. No se repetirá la orden.")
            if status["estado"] == "listo":
                return acknowledgement
            if time.monotonic() >= deadline:
                raise DeviceError("Orden aceptada, pero no se confirmó el retorno. No se repetirá el tiro.")
            time.sleep(0.15)

    def connect_device(self):
        self.connect_job = None
        if self.closed or self.network_busy or self.practice.get():
            return
        self.arena.focus_set()
        self.connected = False
        self.device_client = None
        self.connection_label.config(text="●  SIN CONECTAR", fg=MUTED)
        try:
            client = ESP32Client(self.address.get())
        except DeviceError as error:
            self.network_label.config(text=str(error), fg=RED)
            return
        self.connection_label.config(text="●  CONECTANDO", fg=YELLOW)
        self.network_label.config(text="Comprobando la placa y la versión del minijuego…", fg=MUTED)
        self._begin_task("connect", lambda: (client, client.get_status()))

    def _address_changed(self, *_args):
        self.connected = False
        self.device_client = None
        self.connection_label.config(text="●  SIN CONECTAR", fg=MUTED)
        self.network_label.config(text="IP modificada. Pulsa Conectar para usar esta placa.", fg=MUTED)

    def _begin_task(self, kind: str, job: Callable):
        self.network_busy = True
        self._refresh_controls()

        def worker():
            try:
                self.events.put((kind, True, job()))
            except Exception as error:
                # Ninguna llamada a Tkinter desde este hilo.
                self.events.put((kind, False, str(error)))

        threading.Thread(target=worker, daemon=True, name=f"esp32-{kind}").start()

    def _poll_events(self):
        if self.closed:
            return
        try:
            while True:
                kind, succeeded, result = self.events.get_nowait()
                self.network_busy = False
                if succeeded and kind == "connect":
                    self.device_client, status = result
                    self.connected = True
                    self.connection_label.config(text="●  ESP32 CONECTADO", fg=GREEN)
                    self.network_label.config(text="Listo para jugar. Cada tiro vuelve a reposo después de un segundo.", fg=MUTED)
                elif succeeded and kind == "shot":
                    self.phase = "result"
                    self.detail_label.config(text="Secuencia terminada. ESPACIO para otra ronda.")
                    self.network_label.config(text="El ESP32 confirma el retorno a reposo. Sin reenvíos automáticos.", fg=MUTED)
                else:
                    self.connected = False
                    self.connection_label.config(text="●  REVISAR CONEXIÓN", fg=RED)
                    self.network_label.config(text=result, fg=RED)
                    if kind == "shot":
                        self.phase = "result"
                        self.detail_label.config(text="No se pudo confirmar el tiro. La orden no se repetirá.")
                self._refresh_controls()
        except queue.Empty:
            pass
        self.poll_job = self.root.after(50, self._poll_events)

    def _change_mode(self):
        self.arena.focus_set()
        if self.practice.get():
            self.connection_label.config(text="●  PRÁCTICA", fg=YELLOW)
            self.network_label.config(text="Juega sin enviar órdenes a la catapulta.", fg=MUTED)
        elif self.connected:
            self.connection_label.config(text="●  ESP32 CONECTADO", fg=GREEN)
            self.network_label.config(text="Modo real: detener el marcador enviará el próximo tiro.", fg=MUTED)
        else:
            self.connection_label.config(text="●  SIN CONECTAR", fg=MUTED)
            self.network_label.config(text="Introduce la IP que aparece en Arduino y pulsa Conectar.", fg=MUTED)
        self._refresh_controls()

    def _refresh_controls(self):
        waiting = self.network_busy or self.phase == "sending"
        self.action_button.config(state="disabled" if waiting else "normal",
                                  text="ESPERANDO AL ESP32…" if waiting else
                                  ("OTRA RONDA  ·  ESPACIO" if self.phase == "result" else "DETENER  ·  ESPACIO"))
        self.practice_check.config(state="disabled" if waiting else "normal")
        configuration_state = "disabled" if waiting or self.practice.get() else "normal"
        self.ip_entry.config(state=configuration_state)
        self.connect_button.config(state=configuration_state)

    def close(self):
        if self.closed:
            return
        self.closed = True
        for job in (self.frame_job, self.poll_job, self.connect_job):
            if job is not None:
                self.root.after_cancel(job)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Minijuego de precisión para la catapulta ESP32")
    parser.add_argument("--demo", action="store_true", help="Jugar en modo práctica sin conectar la placa")
    parser.add_argument("--ip", default=DEFAULT_ADDRESS, help="IP o dirección HTTP del ESP32")
    args = parser.parse_args()
    configure_display()
    root = tk.Tk()
    CatapultGame(root, address=args.ip, practice=args.demo)
    root.mainloop()


if __name__ == "__main__":
    main()
