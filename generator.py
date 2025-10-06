from PIL import Image, ImageDraw
import os

def fondo_black_rizos(nombre):
    img = Image.new("RGB", (1024, 768), "#0a0a0a")
    draw = ImageDraw.Draw(img)
    for i in range(6):
        x = 100 + i * 120
        y = 80 + i * 60
        draw.arc([x, y, x+300, y+300], start=0, end=270, fill="#ffd700", width=3)
    img.save(f"static/img/fondo_" + nombre + ".jpg")

def fondo_claro_cuadros(nombre):
    img = Image.new("RGB", (1024, 768), "#e0f7fa")
    draw = ImageDraw.Draw(img)
    for x in range(0, 1024, 64):
        for y in range(0, 768, 64):
            draw.rectangle([x, y, x+60, y+60], outline="#ffffff", width=1)
    img.save(f"static/img/fondo_" + nombre + ".jpg")

def fondo_vibrante_ondas(nombre):
    img = Image.new("RGB", (1024, 768), "#ff4081")
    draw = ImageDraw.Draw(img)
    for i in range(0, 1024, 40):
        draw.arc([i, 100, i+200, 600], start=0, end=180, fill="#ffeb3b", width=4)
    img.save(f"static/img/fondo_" + nombre + ".jpg")

def fondo_elegante_textura(nombre):
    img = Image.new("RGB", (1024, 768), "#2c2c2c")
    draw = ImageDraw.Draw(img)
    for x in range(0, 1024, 20):
        draw.line([(x, 0), (x, 768)], fill="#444444", width=1)
    for y in range(0, 768, 20):
        draw.line([(0, y), (1024, y)], fill="#444444", width=1)
    img.save(f"static/img/fondo_" + nombre + ".jpg")

def fondo_geom_hexagonos(nombre):
    img = Image.new("RGB", (1024, 768), "#e0f2f1")
    draw = ImageDraw.Draw(img)
    for x in range(0, 1024, 60):
        for y in range(0, 768, 52):
            draw.polygon([
                (x+30, y), (x+60, y+15), (x+60, y+45),
                (x+30, y+60), (x, y+45), (x, y+15)
            ], outline="#b2dfdb", fill=None)
    img.save(f"static/img/fondo_" + nombre + ".jpg")

def fondo_organico_curvas(nombre):
    img = Image.new("RGB", (1024, 768), "#80deea")
    draw = ImageDraw.Draw(img)
    for i in range(5):
        draw.pieslice([i*200, 100, i*200+400, 600], start=0, end=180, fill="#4dd0e1")
    img.save(f"static/img/fondo_" + nombre + ".jpg")

# Diccionario de estilos
fondos = {
    "black_rizos": fondo_black_rizos,
    "claro_cuadros": fondo_claro_cuadros,
    "vibrante_ondas": fondo_vibrante_ondas,
    "elegante_textura": fondo_elegante_textura,
    "geom_hexagonos": fondo_geom_hexagonos,
    "organico_curvas": fondo_organico_curvas
}

# Generar todos los fondos
for nombre, funcion in fondos.items():
    funcion(nombre)

