from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs' / 'Guia_montaje_catapulta_ESP32.pdf'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold')
W, H = A4
M = 42
CW = W - 2 * M
INK = colors.HexColor('#20343C')
TEAL = colors.HexColor('#087F82')
MUTED = colors.HexColor('#536971')
LIGHT = colors.HexColor('#EDF5F5')
RED = colors.HexColor('#C83D45')
ORANGE = colors.HexColor('#C47A13')
c = canvas.Canvas(str(OUTPUT), pagesize=A4)
c.setTitle('Catapulta con ESP32 — Guía de montaje')
c.setAuthor('Guía del proyecto catapult_project')
c.setSubject('Piezas, conexiones y puesta en marcha del servo controlado por Wi-Fi')


def para(text, x, top, width, size=10, leading=14, color=INK):
    style = ParagraphStyle('body', fontName='Arial', fontSize=size,
                           leading=leading, textColor=color)
    p = Paragraph(text, style)
    _, height = p.wrap(width, H)
    assert top + height < H - 43, (text, top, height)
    p.drawOn(c, x, H - top - height)
    return top + height


def label(text, x, top, size=10, color=INK, bold=False):
    c.setFillColor(color)
    c.setFont('Arial-Bold' if bold else 'Arial', size)
    c.drawString(x, H - top - size, text)


def line(x1, y1, x2, y2, color=INK, width=1.7):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, H-y1, x2, H-y2)


def wire(points, color):
    c.setStrokeColor(color)
    c.setLineWidth(2.2)
    c.setLineJoin(1)
    c.setLineCap(1)
    path = c.beginPath()
    path.moveTo(points[0][0], H-points[0][1])
    for x, y in points[1:]:
        path.lineTo(x, H-y)
    c.drawPath(path, stroke=1, fill=0)


def box(x, top, width, height, fill=LIGHT):
    c.setFillColor(fill)
    c.roundRect(x, H-top-height, width, height, 8, fill=1, stroke=0)


def heading(text, top):
    label(text, M, top, 13, TEAL, True)
    return top + 25


def header(kicker, title, subtitle):
    label(kicker, M, 31, 8.5, TEAL, True)
    label(title, M, 51, 24, INK, True)
    para(subtitle, M, 89, CW, 10, 14, MUTED)


def footer(page):
    line(M, H-35, W-M, H-35, colors.HexColor('#D5E1E3'), .7)
    label('CATAPULTA · ESP32 + PYTHON', M, H-26, 8, MUTED)
    c.setFont('Arial', 8)
    c.setFillColor(MUTED)
    c.drawRightString(W-M, 18, f'{page} / 2')


header('GUÍA RÁPIDA / 01', 'Piezas y conexiones',
       'Montaje para el proyecto actual: un servo en GPIO26, controlado desde Python por Wi-Fi.')
y = heading('1. Material necesario', 125)
rows = [
    ('Cant.', 'Pieza', 'Qué comprobar'),
    ('1', 'ESP32 Dev Module', 'Placa ESP32 clásica, con GPIO26 accesible.'),
    ('1', 'Servo de posición', 'De unos 180°, apto para 5 V y señal de 3,3 V. No de rotación continua.'),
    ('1', 'Fuente regulada para el servo', '5 V si su ficha lo admite; corriente suficiente para arranque y bloqueo. Depende del modelo.'),
    ('1', 'Cable USB de datos', 'Conector compatible con tu placa; alimenta y programa el ESP32.'),
    ('—', 'Cables y conectores', 'Dupont para señal; cable y bornera adecuados a la corriente del servo para alimentación.'),
    ('1 kit', 'Estructura mecánica', 'Base, soporte del servo, brazo ligero, horn y tornillo del servo, cazoleta y pelota blanda.'),
    ('1 + 1', 'PC y router Wi-Fi', 'Windows, Arduino IDE, Python 3.12 con Tkinter y red Wi-Fi de 2,4 GHz.'),
]
cell_style = ParagraphStyle('cell', fontName='Arial', fontSize=9.2, leading=12, textColor=INK)
cells = [[Paragraph(f'<b>{v}</b>' if i == 0 else v, cell_style) for v in row]
         for i, row in enumerate(rows)]
t = Table(cells, colWidths=[39, 155, CW-194])
t.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (-1, -1), 7),
    ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#DCE6E8')),
]))
_, th = t.wrap(CW, H)
t.drawOn(c, M, H-y-th)
y += th + 12
y = para('No necesitas un pulsador ni un módulo Wi-Fi adicional. La fuerza del servo debe ser suficiente para tu brazo; el modelo exacto no figura en el proyecto.', M, y, CW, 9.2, 12) + 15
y = heading('2. Cableado: hazlo con todo apagado', y)

# Logical schematic, not a physical pinout: label names are the reference.
dy = y
box(42, dy, 174, 113)
label('ESP32', 54, dy+10, 13, TEAL, True)
label('USB al PC', 54, dy+33, 10)
label('GPIO26', 152, dy+60, 9, INK, True)
label('GND', 172, dy+88, 9, INK, True)
box(420, dy+43, 132, 112)
label('SERVO', 434, dy+52, 13, TEAL, True)
label('Señal', 434, dy+79, 9)
label('V+ (5 V)', 434, dy+106, 9)
label('GND', 434, dy+132, 9)
box(42, dy+148, 174, 63)
label('FUENTE EXTERNA', 54, dy+158, 10, TEAL, True)
label('5 V CC regulados', 54, dy+177, 9)
label('+', 197, dy+165, 11, RED, True)
label('−', 197, dy+191, 11, INK, True)

wire([(216,dy+67), (299,dy+67), (299,dy+86), (420,dy+86)], ORANGE)
label('Señal de control', 304,dy+68, 8, ORANGE)
wire([(216,dy+173), (363,dy+173), (363,dy+113), (420,dy+113)], RED)
label('+5 V', 368,dy+97, 8, RED)
wire([(216,dy+95), (258,dy+95), (258,dy+199)], INK)
wire([(216,dy+199), (399,dy+199), (399,dy+139), (420,dy+139)], INK)
c.setFillColor(INK)
c.circle(258,H-(dy+199),3,fill=1,stroke=0)
label('GND común', 284,dy+204, 9, INK, True)
y = dy + 231
y = para('<b>Colores habituales del servo:</b> rojo = V+; marrón/negro = GND; amarillo/naranja/blanco = señal. Confirma su ficha antes de conectar. Busca <b>GPIO26 o IO26</b> en la placa: no es el pin físico número 26. [1, 2]', M, y, CW, 9.2, 12) + 8
y = para('<b>Alimentación:</b> ESP32 por USB y servo por su fuente; une las masas. No alimentes el servo desde 3V3 ni un GPIO. En este montaje, el positivo de la fuente externa va solo al servo, no al ESP32. [1, 2]', M, y, CW, 9.2, 12)
footer(1)
c.showPage()

header('GUÍA RÁPIDA / 02', 'Montaje y primer tiro',
       'Usa los archivos que ya están en esta carpeta. No hace falta añadir un botón físico.')
y = 128


def step(number, title, text, top):
    box(M, top, 24, 24)
    label(str(number), M+8, top+4, 11, TEAL, True)
    label(title, M+35, top+2, 11, INK, True)
    bottom = para(text, M+35, top+22, CW-35, 9.7, 13.2)
    return bottom + 15


y = step(1, 'Prepara la mecánica y los cables',
         'Fija el servo a una base estable y deja el brazo desmontado. Con USB y fuente desconectados, cablea según la página 1. El brazo debe poder recorrer 0–120° sin topar ni forzar el mecanismo.', y)
y = step(2, 'Prepara Arduino IDE',
         'En el gestor de placas instala <b>esp32 by Espressif Systems</b>; en el gestor de bibliotecas, <b>ESP32Servo</b>. Si no aparece la placa, añade en Preferencias → URLs adicionales de placas el <a href="https://espressif.github.io/arduino-esp32/package_esp32_index.json" color="#087F82"><u>índice oficial de ESP32</u></a>. Selecciona <b>ESP32 Dev Module</b>. [3, 4]', y)
y = step(3, 'Carga el programa en la placa',
         'Conecta el USB al PC, selecciona su puerto COM y abre <b>catapult_code/sketch_aug19a/sketch_aug19a.ino</b>. Copia <b>wifi_config.h.example</b> como <b>wifi_config.h</b>, rellena allí tu red y contraseña y pulsa Subir. Mantén apagada la fuente del servo durante la carga.', y)
y = step(4, 'Coloca el brazo en su posición de reposo',
         'Con el programa cargado y el ESP32 encendido, enciende la fuente del servo sin el brazo: se situará en <b>120°</b>. Apaga ambas alimentaciones y monta el brazo en el <b>horn</b> (pieza que encaja en el eje), orientado para el reposo, sin girar el eje a mano. Aprieta su tornillo.', y)
y = step(5, 'Conecta el juego por Wi-Fi',
         'Enciende todo. Abre el monitor serie a <b>115200 baudios</b> y pulsa <b>EN/RESET</b> para ver la IP. Conecta el PC a la misma red local. Desde esta carpeta, ejecuta en PowerShell:', y)
box(M+35, y-7, CW-35, 27)
label('py python_code/app_catapulta.py', M+47, y, 10, TEAL, True)
y += 27
y = para('En la aplicación, escribe la IP que aparece en el monitor y pulsa <b>Conectar</b>. Para mover la catapulta, desactiva <b>Práctica</b>. Las órdenes viajan por HTTP sobre Wi-Fi.', M+35, y, CW-35, 9.7, 13.2)+15
y = step(6, 'Haz la primera prueba',
         'Prueba primero sin carga y con el recorrido despejado. Pulsa <b>Espacio</b> para parar la barra y disparar; vuelve a pulsarlo para otra ronda. En el centro: <b>120° → 0° → 120°</b>. En el borde: <b>120° → 108° → 120°</b>. El retorno se ordena tras 1 segundo. El porcentaje regula el recorrido angular, no una fuerza medida.', y)
y = heading('Si algo falla', y+1)
y = para('<b>No aparece el puerto:</b> prueba un cable USB de datos; revisa el controlador USB de tu placa. <b>Servo que tiembla o placa que se reinicia:</b> revisa fuente, conexiones y GND común. <b>No conecta:</b> comprueba Wi-Fi de 2,4 GHz, IP actual y que el router permita comunicación entre dispositivos.', M, y, CW, 9.2, 12)+12
y = para('<b>Fuentes de consulta</b> · enlaces pulsables<br/>[1] <a href="https://learn.adafruit.com/using-servos-with-circuitpython/hardware" color="#087F82">Adafruit: cableado y alimentación del servo</a> · [2] <a href="https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html" color="#087F82">Espressif: placa ESP32</a><br/>[3] <a href="https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html" color="#087F82">Espressif: instalación en Arduino IDE</a> · [4] <a href="https://github.com/madhephaestus/ESP32Servo" color="#087F82">Biblioteca ESP32Servo</a>', M, y, CW, 8.1, 11, MUTED)
footer(2)
c.save()
print(OUTPUT)
print(f'Page 2 content ends at {y:.1f} pt (page height {H:.1f} pt)')
