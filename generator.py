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
        imagen = config['imagen'] or 'default.jpg'
        origen = os.path.join('static', 'img', imagen)
        destino = os.path.join(carpeta, 'img', imagen)
        if os.path.exists(origen):
            shutil.copy(origen, destino)

    # index.html
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{config['descripcion'] or 'Sitio generado automáticamente'}">
    <title>{config['titulo'] or 'Mi sitio'}</title>
    <link rel="stylesheet" href="style.css">
    <link rel="icon" href="img/{config['imagen'] or 'default.jpg'}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

<div class="container py-5">
"""

    # Hero principal
    html += f"""
<div class="text-center mb-5">
    <img src="img/{config['imagen'] or 'default.jpg'}" class="img-fluid rounded shadow" style="max-height: 300px;">
    <h1 class="mt-4">{config['titulo'] or 'Bienvenido'}</h1>
    <p class="lead">{config['descripcion'] or ''}</p>
</div>
"""

    # Catálogo o contenido
    if config['tipo_web'] == 'catálogo':
        html += '<div class="row">'
        for p in config['productos']:
            html += f"""
<div class="col-md-4 mb-4">
    <div class="card h-100 shadow-sm">
        <img src="img/{p['imagen']}" class="card-img-top" alt="{p['nombre']}">
        <div class="card-body">
            <h5 class="card-title">{p['nombre']}</h5>
            <p class="card-text">{p['descripcion']}</p>
            {'<p class="text-success fw-bold">' + p['precio'] + '</p>' if p['precio'] else ''}
        </div>
    </div>
</div>
"""
        html += '</div>'
    else:
        html += '<div class="text-center mb-5">'
        html += f"<p>{config['descripcion']}</p>"
        html += '</div>'

    # Contacto
    if config['contacto'] == 'sí':
        html += """
<div class="text-center my-4">
    <form class="d-inline-block">
        <input type="text" class="form-control mb-2" placeholder="Tu mensaje">
        <button class="btn btn-primary">Enviar</button>
    </form>
</div>
"""

    # WhatsApp
    if config['whatsapp'] == 'sí':
        html += """
<div class="text-center my-2">
    <a href="https://wa.me/549XXXXXXXXXX" class="btn btn-success">
        Contactar por WhatsApp
    </a>
</div>
"""

    # Pago
    if config['pago'] != 'ninguno':
        html += f"""
<div class="text-center my-2">
    <p><strong>Medio de pago:</strong> {config['pago']}</p>
</div>
"""

    # Footer
    html += f"""
<footer class="text-center mt-5 text-muted">
    <hr>
    <p>&copy; {config['titulo'] or 'Mi sitio'} - Generado automáticamente</p>
</footer>
</div>
</body>
</html>
"""

    with open(os.path.join(carpeta, 'index.html'), 'w') as f:
        f.write(html)

    # style.css
    css = f"""body {{
    font-family: {config['fuente']};
    color: #333;
}}
h1 {{
    color: {config['color']};
}}
.btn-primary {{
    background-color: {config['color']};
    border: none;
}}
.btn {{
    border-radius: {"10px" if config['botones'] == "redondeado" else "0px"};
    box-shadow: {"2px 2px 5px gray" if config['botones'] == "sombra" else "none"};
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

    # ZIP final
    zip_path = 'user_sites/sitio_final.zip'
    shutil.make_archive('user_sites/sitio_final', 'zip', root_dir=carpeta)
    return zip_path
