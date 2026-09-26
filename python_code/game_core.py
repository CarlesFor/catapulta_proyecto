"""Reglas del minijuego y cliente HTTP, sin depender de la interfaz gráfica."""

from dataclasses import dataclass
from http.client import HTTPException
import ipaddress
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


@dataclass(frozen=True)
class Shot:
    position: float
    factor: float
    travel_degrees: float
    target_degrees: float
    rating: str


def calculate_shot(position: float) -> Shot:
    """Convierte la posición 0..1 en un recorrido simétrico de 12..120°."""
    try:
        position = float(position)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("La posición debe ser un número finito.") from error
    if not math.isfinite(position):
        raise ValueError("La posición debe ser un número finito.")

    position = max(0.0, min(1.0, position))
    factor = 0.1 + 0.9 * (1.0 - abs(2.0 * position - 1.0))
    travel = 120.0 * factor
    if factor >= 0.995:
        rating = "¡TIRO PERFECTO!"
    elif factor >= 0.9:
        rating = "¡CASI PERFECTO!"
    elif factor >= 0.7:
        rating = "¡BUEN TIRO!"
    elif factor >= 0.4:
        rating = "PUEDES AFINAR MÁS"
    else:
        rating = "¡OTRA OPORTUNIDAD!"

    return Shot(position, factor, travel, 120.0 - travel, rating)


class DeviceError(Exception):
    """Una conexión, petición o respuesta del dispositivo no es válida."""


def normalize_address(address: str) -> str:
    """Acepta un host/IP y puerto opcional; devuelve una URL base HTTP."""
    if not isinstance(address, str):
        raise DeviceError("Introduce la IP o el nombre del ESP32.")
    address = address.strip()
    if not address or any(character.isspace() or ord(character) < 32 for character in address):
        raise DeviceError("Introduce una dirección sin espacios, por ejemplo 192.0.2.1.")

    candidate = address if "://" in address else "http://" + address
    try:
        parts = urlsplit(candidate)
        hostname = parts.hostname
        port = parts.port
    except ValueError as error:
        raise DeviceError("La dirección o el puerto del ESP32 no son válidos.") from error
    if (
        parts.scheme != "http"
        or not hostname
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or "?" in candidate
        or "#" in candidate
        or parts.netloc.endswith(":")
        or port == 0
    ):
        raise DeviceError("Usa solo http://IP:puerto, sin rutas, credenciales ni parámetros.")

    if ":" in hostname:
        try:
            ipaddress.IPv6Address(hostname)
        except ValueError as error:
            raise DeviceError("La dirección IPv6 no es válida.") from error
        host = "[" + hostname + "]"
    else:
        labels = hostname.rstrip(".").split(".")
        if len(hostname) > 253 or any(
            not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
            for label in labels
        ):
            raise DeviceError("La IP o el nombre del ESP32 no son válidos.")
        host = hostname

    suffix = f":{port}" if port is not None else ""
    return f"http://{host}{suffix}"


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        # Una orden al servo debe producir una sola petición al destino indicado.
        return None


class ESP32Client:
    def __init__(self, address: str, timeout: float = 3):
        self.address = normalize_address(address)
        try:
            self.timeout = float(timeout)
        except (TypeError, ValueError, OverflowError) as error:
            raise DeviceError("El tiempo de espera debe ser un número positivo.") from error
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise DeviceError("El tiempo de espera debe ser un número positivo.")
        self._opener = build_opener(_NoRedirects())

    def get_status(self) -> dict:
        status, data = self._request("GET", "/estado")
        if status != 200:
            raise DeviceError(f"El ESP32 devolvió un estado HTTP inesperado: {status}.")
        if type(data.get("api_version")) is not int or data["api_version"] != 1:
            raise DeviceError("Firmware incompatible. Carga el firmware del minijuego (API 1).")
        if data.get("estado") not in ("listo", "disparando"):
            raise DeviceError("El ESP32 devolvió un estado desconocido.")
        return data

    def fire(self, factor: float, shot_id: str) -> dict:
        try:
            factor = float(factor)
        except (TypeError, ValueError, OverflowError) as error:
            raise DeviceError("La potencia debe estar entre 0.1 y 1.") from error
        if not math.isfinite(factor) or not 0.1 <= factor <= 1.0:
            raise DeviceError("La potencia debe estar entre 0.1 y 1.")
        if not isinstance(shot_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", shot_id):
            raise DeviceError("El identificador del tiro debe tener 1..64 letras, números, guiones o subrayados.")

        body = urlencode({"potencia": f"{factor:.6f}", "id": shot_id}).encode("ascii")
        status, data = self._request("POST", "/disparar", body)
        if status != 202 or data.get("aceptado") is not True or data.get("id") != shot_id:
            raise DeviceError("No se pudo confirmar el tiro: la respuesta no coincide con la orden enviada.")
        return data

    def _request(self, method: str, path: str, body: bytes | None = None) -> tuple[int, dict]:
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(self.address + path, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status = response.status
                payload = response.read()
        except HTTPError as error:
            detail = ""
            try:
                with error:
                    problem = json.loads(error.read().decode("utf-8"))
                if isinstance(problem, dict) and isinstance(problem.get("error"), str):
                    detail = ": " + problem["error"]
            except (ValueError, UnicodeError, OSError, HTTPException):
                pass
            raise DeviceError(f"El ESP32 respondió HTTP {error.code}{detail}.") from error
        except (URLError, OSError, HTTPException) as error:
            detail = str(getattr(error, "reason", error))
            if method == "POST":
                message = "No se pudo confirmar el tiro; la orden podría haber llegado al ESP32"
            else:
                message = "No se pudo conectar con el ESP32"
            raise DeviceError(f"{message}: {detail}.") from error

        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise DeviceError("El ESP32 no devolvió JSON válido. Comprueba que tiene el firmware del minijuego.") from error
        if not isinstance(data, dict):
            raise DeviceError("La respuesta del ESP32 debe ser un objeto JSON.")
        return status, data
