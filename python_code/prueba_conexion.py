import argparse
from urllib.request import urlopen

from game_core import normalize_address


def main():
    parser = argparse.ArgumentParser(description="Comprueba la conexion con el ESP32")
    parser.add_argument("--ip", required=True, help="IP del ESP32 indicada en el monitor serie")
    args = parser.parse_args()
    url = normalize_address(args.ip) + "/estado"
    with urlopen(url, timeout=5) as respuesta:
        texto = respuesta.read().decode("utf-8")
        print("Codigo HTTP:", respuesta.status)
        print("Respuesta del ESP32:", texto)


if __name__ == "__main__":
    main()
