from PIL import Image, ImageDraw
import os
import math
import random

def fondo_black_rizos(nombre):
    os.makedirs("static/img", exist_ok=True)
    for variant in range(10):
        img = Image.new("RGB", (1024, 768), "#0a0a0a")
        draw = ImageDraw.Draw(img)
        random.seed(variant)
        base_angle = random.randint(0, 360)
        scale_factor = random.uniform(0.8, 1.2)
        thickness = random.randint(2, 6)
        
        for i in range(6):
            x = 100 + i * 120 * scale_factor
            y = 80 + i * 60 * scale_factor
            for j in range(3):
                start_angle = base_angle + j * 30
                end_angle = start_angle + 270 + random.randint(-30, 30)
                size = 300 + j * 50 * scale_factor
                color = (255 - j * 20, 215 - j * 30, 0)
                draw.arc([x, y, x + size, y + size], start=start_angle, end=end_angle, fill=color, width=thickness + j)
            for k in range(2):
                detail_size = size * 0.6 + k * 20
                draw.arc([x + size * 0.2, y + size * 0.2, x + detail_size, y + detail_size], start=start_angle + 45, end=end_angle - 45, fill="#b8860b", width=1)
            for angle in range(0, 360, 60):
                rad = math.radians(angle + base_angle)
                length = size * 0.4
                x_end = x + size / 2 + math.cos(rad) * length
                y_end = y + size / 2 + math.sin(rad) * length
                draw.line([(x + size / 2, y + size / 2), (x_end, y_end)], fill="#daa520", width=1)
            for _ in range(5):
                point_x = x + size / 2 + random.randint(-size // 2, size // 2)
                point_y = y + size / 2 + random.randint(-size // 2, size // 2)
                draw.ellipse([point_x - 3, point_y - 3, point_x + 3, point_y + 3], fill="#ffd700")
        img.save(f"static/img/fondo_{nombre}_variant_{variant + 1}.jpg")

def fondo_claro_cuadros(nombre):
    os.makedirs("static/img", exist_ok=True)
    for variant in range(10):
        img = Image.new("RGB", (1024, 768), "#e0f7fa")
        draw = ImageDraw.Draw(img)
        random.seed(variant)
        grid_size = random.randint(50, 80)
        color_shift = random.randint(0, 50)
        
        for x in range(0, 1024, grid_size):
            for y in range(0, 768, grid_size):
                fill_color = (200 - color_shift, 240 - color_shift, 250 - color_shift) if (x // grid_size + y // grid_size) % 2 == 0 else "#e0f7fa"
                draw.rectangle([x, y, x + grid_size - 4, y + grid_size - 4], fill=fill_color, outline="#ffffff", width=2)
                if random.random() > 0.7:
                    draw.ellipse([x + 5, y + 5, x + 15, y + 15], fill="#80deea")
            draw.line([(x, 0), (x, 768)], fill="#b2ebf2", width=1, joint="curve")
        for y in range(0, 768, grid_size):
            draw.line([(0, y), (1024, y)], fill="#b2ebf2", width=1, joint="curve")
        img.save(f"static/img/fondo_{nombre}_variant_{variant + 1}.jpg")

def fondo_vibrante_ondas(nombre):
    os.makedirs("static/img", exist_ok=True)
    for variant in range(10):
        img = Image.new("RGB", (1024, 768), "#ff4081")
        draw = ImageDraw.Draw(img)
        random.seed(variant)
        wave_spacing = random.randint(30, 50)
        base_angle = random.randint(0, 180)
        
        for i in range(0, 1024, wave_spacing):
            color = (255, 235 - i % 50, 59 + i % 50)
            for j in range(3):
                draw.arc([i, 100 + j * 50, i + 200, 600 + j * 50], start=base_angle, end=base_angle + 180 + random.randint(-20, 20), fill=color, width=4 + j)
                draw.ellipse([i + 100, 600 + j * 50 - 5, i + 110, 600 + j * 50 + 5], fill="#ffffff")
            draw.line([(i, 100), (i + 100, 600)], fill="#ffca28", width=1)
        img.save(f"static/img/fondo_{nombre}_variant_{variant + 1}.jpg")

def fondo_elegante_textura(nombre):
    os.makedirs("static/img", exist_ok=True)
    for variant in range(10):
        img = Image.new("RGB", (1024, 768), "#2c2c2c")
        draw = ImageDraw.Draw(img)
        random.seed(variant)
        line_spacing = random.randint(15, 25)
        
        for x in range(0, 1024, line_spacing):
            for y in range(0, 768, line_spacing):
                color = (68 + random.randint(-10, 10), 68 + random.randint(-10, 10), 68 + random.randint(-10, 10))
                draw.rectangle([x, y, x + line_spacing - 2, y + line_spacing - 2], fill=color)
                if random.random() > 0.8:
                    draw.ellipse([x + 2, y + 2, x + 8, y + 8], fill="#888888")
            draw.line([(x, 0), (x, 768)], fill="#555555", width=2)
        for y in range(0, 768, line_spacing):
            draw.line([(0, y), (1024, y)], fill="#555555", width=2)
        img.save(f"static/img/fondo_{nombre}_variant_{variant + 1}.jpg")

def fondo_geom_hexagonos(nombre):
    os.makedirs("static/img", exist_ok=True)
    for variant in range(10):
        img = Image.new("RGB", (1024, 768), "#e0f2f1")
        draw = ImageDraw.Draw(img)
        random.seed(variant)
        hex_size = random.randint(50, 70)
        
        for x in range(0, 1024, int(hex_size * 1.5)):
            for y in range(0, 768, hex_size):
                color = (178 + random.randint(-20, 20), 223 + random.randint(-20, 20), 219 + random.randint(-20, 20))
                points = [
                    (x + hex_size / 2, y), (x + hex_size, y + hex_size * 0.3),
                    (x + hex_size, y + hex_size * 0.7), (x + hex_size / 2, y + hex_size),
                    (x, y + hex_size * 0.7), (x, y + hex_size * 0.3)
                ]
                draw.polygon(points, outline="#4db6ac", fill=color if random.random() > 0.5 else None)
                if random.random() > 0.6:
                    draw.ellipse([x + hex_size / 4, y + hex_size / 4, x + hex_size * 0.75, y + hex_size * 0.75], fill="#26a69a")
        img.save(f"static/img/fondo_{nombre}_variant_{variant + 1}.jpg")

def fondo_organico_curvas(nombre):
    os.makedirs("static/img", exist_ok=True)
    for variant in range(10):
        img = Image.new("RGB", (1024, 768), "#80deea")
        draw = ImageDraw.Draw(img)
        random.seed(variant)
        offset = random.randint(150, 250)
        
        for i in range(5):
            color = (77 + random.randint(-20, 20), 208 + random.randint(-20, 20), 225 + random.randint(-20, 20))
            draw.pieslice([i * offset, 100, i * offset + 400, 600], start=0, end=180 + random.randint(-30, 30), fill=color)
            for j in range(2):
                draw.ellipse([i * offset + 100 + j * 50, 300, i * offset + 150 + j * 50, 350], fill="#ffffff")
            draw.line([(i * offset + 200, 100), (i * offset + 200, 600)], fill="#26c6da", width=2)
        img.save(f"static/img/fondo_{nombre}_variant_{variant + 1}.jpg")

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
