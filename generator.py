import os
import shutil

def generar_sitio(config):
    carpeta = 'user_sites/temp'
    os.makedirs(os.path.join(carpeta, 'img'), exist_ok=True)

    # Copiar imágenes
    if config['tipo_web'] == 'catálogo':
        for producto in config['productos']:
            origen = os.path.join('static', 'img', producto['imagen'])
            destino = os.path.join(carpeta, 'img', producto['imagen'])
            if os.path.exists(origen):
                shutil.copy(origen, destino)
    else:
        origen = os.path.join('static', 'img', config['imagen'] or 'default.jpg')
        destino = os.path.join(carpeta, 'img', config['imagen'] or 'default.jpg')
        if os.path.exists(origen):
            shutil.copy(origen, destino)

    # index.html
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{config['titulo'] or 'Mi sitio'}</title>
    <link rel="stylesheet" href="style.css">
    <link rel="icon" href="img/{config['imagen'] or 'default.jpg'}">
</head>
<body class="container">
"""

    if config['tipo_web'] == 'catálogo':
        html += "<h1>Catálogo de productos</h1>\n"
        for p in config['productos']:
            html += f"""
<div class="producto card">
    <h2>{p['nombre']}</h2>
    <img src="img/{p['imagen']}" width="200">
    <p>{p['descripcion']}</p>
    <p><strong>{p['precio'] or ''}</strong></p>
</div>
"""
    else:
        html += f"""
<h1>{config['titulo']}</h1>
<img src="img/{config['imagen'] or 'default.jpg'}" width="300">
<p>{config['descripcion']}</p>
"""

    if config['contacto'] == 'sí':
        html += "<form><input type='text' placeholder='Tu mensaje'><button>Enviar</button></form>\n"
    if config['whatsapp'] == 'sí':
        html += "<a href='https://wa.me/549XXXXXXXXXX'>WhatsApp</a>\n"
    if config['pago'] != 'ninguno':
        html += f"<p>Medio de pago: {config['pago']}</p>\n"

    html += "</body></html>"

    with open(os.path.join(carpeta, 'index.html'), 'w') as f:
        f.write(html)

    # style.css
    css = f"""body {{
    background-color: #f4f4f4;
    font-family: {config['fuente']};
    color: #333;
    max-width: 800px;
    margin: auto;
    padding: 20px;
    line-height: 1.6;
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
.producto img {{
    border-radius: 8px;
    box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
}}
"""
    with open(os.path.join(carpeta, 'style.css'), 'w') as f:
        f.write(css)

    # README.md
    readme = f"""# Sitio generado automáticamente

Tipo de sitio: {config['tipo_web']}
Color: {config['color']}
Fuente: {config['fuente']}
Botones: {config['botones']}
Contacto: {config['contacto']}
WhatsApp: {config['whatsapp']}
Pago: {config['pago']}
"""
    with open(os.path.join(carpeta, 'README.md'), 'w') as f:
        f.write(readme)

    # ✅ ZIP con imágenes incluidas
    zip_path = 'user_sites/sitio_final.zip'
    shutil.make_archive('user_sites/sitio_final', 'zip', root_dir=carpeta)
    return zip_path
