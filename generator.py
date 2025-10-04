import os
import shutil

def generar_sitio(config):
    carpeta = 'user_sites/temp'
    os.makedirs(os.path.join(carpeta, 'img'), exist_ok=True)

    # Copiar imagen
    origen = os.path.join('static', 'img', config['imagen'])
    destino = os.path.join(carpeta, 'img', config['imagen'])
    if os.path.exists(origen):
        shutil.copy(origen, destino)

    # index.html
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{config['titulo']}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>{config['titulo']}</h1>
    <img src="img/{config['imagen']}" alt="Imagen destacada" width="300"><br>
    <p>{config['descripcion']}</p>
    {"<form><input type='text' placeholder='Tu mensaje'><button>Enviar</button></form>" if config['contacto'] == "sí" else ""}
    {"<a href='https://wa.me/549XXXXXXXXXX'>WhatsApp</a>" if config['whatsapp'] == "sí" else ""}
    {"<p>Medio de pago: " + config['pago'] + "</p>" if config['pago'] != "ninguno" else ""}
</body>
</html>
"""
    with open(os.path.join(carpeta, 'index.html'), 'w') as f:
        f.write(html)

    # style.css
    css = f"""body {{
    background-color: #f4f4f4;
    font-family: {config['fuente']};
    color: #333;
}}
h1 {{
    color: {config['color']};
}}
button {{
    background-color: {config['color']};
    color: white;
    border-radius: {"10px" if config['botones'] == "redondeado" else "0px"};
    box-shadow: {"2px 2px 5px gray" if config['botones'] == "sombra" else "none"};
    padding: 10px;
}}
"""
    with open(os.path.join(carpeta, 'style.css'), 'w') as f:
        f.write(css)

    # README.md
    readme = f"""# Sitio generado automáticamente

Este sitio fue creado con la app paso a paso.

## Cómo usarlo

1. Subí estos archivos a [Render](https://render.com).
2. Activá UptimeRobot si querés que esté siempre activo.
3. Personalizá el contenido si lo necesitás.

Tipo de sitio: {config['tipo_web']}
Color principal: {config['color']}
Fuente: {config['fuente']}
Botones: {config['botones']}
Contacto: {config['contacto']}
WhatsApp: {config['whatsapp']}
Pago: {config['pago']}
"""
    with open(os.path.join(carpeta, 'README.md'), 'w') as f:
        f.write(readme)

    # Comprimir
    zip_path = 'user_sites/sitio_final.zip'
    shutil.make_archive('user_sites/sitio_final', 'zip', carpeta)
    return zip_path
