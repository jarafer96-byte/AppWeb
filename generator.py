import os
from zipfile import ZipFile

def generar_sitio(session):
    tipo = session.get('tipo_web')
    color = session.get('color')
    fuente = session.get('fuente')
    estilo = session.get('estilo')
    bordes = session.get('bordes')
    botones = session.get('botones')
    idioma = session.get('idioma')
    vista = session.get('vista_imagenes')
    logo = session.get('logo')
    bloques = session.get('bloques')

    textos = {
        'es': {'contacto': 'Contactar por WhatsApp', 'precio': 'Precio'},
        'en': {'contacto': 'Contact via WhatsApp', 'precio': 'Price'},
        'pt': {'contacto': 'Contato via WhatsApp', 'precio': 'Preço'}
    }

    css = f"""body {{
        font-family: '{fuente}', sans-serif;
        background-color: {"#f8f9fa" if estilo != "oscuro" else "#1c1c1c"};
        color: {"#333" if estilo != "oscuro" else "#eee"};
    }}
    .card {{
        border-radius: {"1rem" if bordes == "redondeado" else "0"};
        box-shadow: {"0 4px 8px rgba(0,0,0,0.1)" if bordes == "sombra" else "none"};
        border: {"none" if bordes == "sombra" else "1px solid #ccc"};
    }}
    .btn {{
        border-radius: {"50px" if botones == "pill" else "0"};
        box-shadow: {"2px 2px 5px rgba(0,0,0,0.2)" if botones == "sombra" else "none"};
    }}
    .btn-primary {{
        background-color: {color};
        border: none;
    }}"""

    html = f"""<!DOCTYPE html>
<html lang="{idioma}">
<head>
  <meta charset="UTF-8">
  <title>Mi sitio personalizado</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family={fuente}&display=swap" rel="stylesheet">
  <style>{css}</style>
</head>
<body>
  <div class="container py-5 text-center">
    {f'<img src="img/{logo}" style="max-height:80px;" class="mb-3">' if logo else ''}
    <h1 style="color:{color}">Mi sitio personalizado</h1>
    <p class="lead">Este sitio fue generado automáticamente.</p>
  </div>
  <div class="container">
"""

    if tipo in ['catálogo', 'menú']:
        html += '<div class="row">'
        for p in bloques:
            img_class = {
                'grid': 'card-img-top',
                'fila': 'img-fluid w-100',
                'mini': 'img-thumbnail'
            }.get(vista, 'card-img-top')

            html += f"""
            <div class="col-md-4 mb-4">
              <div class="card h-100">
                <img src="img/{p['imagen']}" class="{img_class}">
                <div class="card-body">
                  <h5 class="card-title">{p['nombre']}</h5>
                  <p class="card-text">{p['descripcion']}</p>
                  <p class="text-success fw-bold">{textos[idioma]['precio']}: {p['precio']}</p>
                </div>
              </div>
            </div>
            """
        html += '</div>'

    elif tipo == 'presentación':
        for p in bloques:
            html += f"""
            <div class="card p-4 mb-4 text-center">
              <img src="img/{p['foto']}" class="img-fluid rounded mb-3">
              <h3>{p['titulo']}</h3>
              <p>{p['texto']}</p>
            </div>
            """

    elif tipo == 'evento':
        for p in bloques:
            html += f"""
            <div class="card p-4 mb-4 text-center">
              <img src="img/{p['imagen_evento']}" class="img-fluid rounded mb-3">
              <h3>{p['nombre_evento']}</h3>
              <p>{p['descripcion_evento']}</p>
              <p><strong>{p['fecha']}</strong> — {p['ubicacion']}</p>
              <a href="#" class="btn btn-primary mt-2">{textos[idioma]['contacto']}</a>
            </div>
            """

    html += """
    <div class="text-center mt-5">
      <p class="text-muted">Sitio generado por Copilot y Fernando</p>
    </div>
  </div>
</body>
</html>
"""

    os.makedirs('sitio_final/img', exist_ok=True)
    with open('sitio_final/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    for p in bloques:
        for key in p:
            if 'imagen' in key and p[key]:
                src = os.path.join('static/img', p[key])
                dst = os.path.join('sitio_final/img', p[key])
                if os.path.exists(src):
                    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                        fdst.write(fsrc.read())

    if logo:
        src = os.path.join('static/img', logo)
        dst = os.path.join('sitio_final/img', logo)
        if os.path.exists(src):
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                fdst.write(fsrc.read())

    zip_path = 'sitio_final.zip'
    with ZipFile(zip_path, 'w') as zipf:
        for folder, _, files in os.walk('sitio_final'):
            for file in files:
                full_path = os.path.join(folder, file)
                rel_path = os.path.relpath(full_path, 'sitio_final')
                zipf.write(full_path, rel_path)

    return zip_path
