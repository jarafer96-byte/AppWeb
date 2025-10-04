from PIL import Image, ImageDraw, ImageFont, ImageColor
import os
from generator import estilos

# Carpeta de salida
output_dir = "static/img"
os.makedirs(output_dir, exist_ok=True)

# Fuente por defecto (puede cambiarse si tenés una TTF local)
try:
    font = ImageFont.truetype("arial.ttf", 24)
except:
    font = ImageFont.load_default()

def crear_preview(nombre, fondo):
    # Manejar gradientes (no renderizables)
    if fondo.startswith("linear-gradient"):
        color = (100, 100, 100)  # gris neutro
    else:
        try:
            color = ImageColor.getrgb(fondo)
        except:
            color = (50, 50, 50)  # fallback

    # Crear imagen
    img = Image.new("RGB", (400, 300), color)
    draw = ImageDraw.Draw(img)
    texto = nombre.replace("_", " ").title()
    text_width, text_height = draw.textsize(texto, font=font)
    x = (400 - text_width) // 2
    y = (300 - text_height) // 2
    draw.text((x, y), texto, fill="white", font=font)

    # Guardar imagen
    filename = f"{output_dir}/preview_{nombre}.jpg"
    img.save(filename)
    print(f"✅ Generado: {filename}")

# Recorrer todos los estilos
for nombre, config in estilos.items():
    crear_preview(nombre, config["fondo"])
