from flask import Flask, render_template, request, redirect, session, send_file
import os
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.secret_key = 'clave-secreta'

UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Compresión y redimensionado
def convertir_y_comprimir(imagen, destino, calidad=50, max_size=(400, 400)):
    img = Image.open(imagen)
    img = img.convert('RGB')
    img.thumbnail(max_size)
    img.save(destino, format='WEBP', quality=calidad)

# ✅ Redimensiona automáticamente los fondos .webp al iniciar
def redimensionar_webp_en_static():
    carpeta = 'static/img/webp'
    for nombre in os.listdir(carpeta):
        if nombre.endswith('.webp'):
            ruta = os.path.join(carpeta, nombre)
            try:
                img = Image.open(ruta)
                img = img.convert('RGB')
                img.thumbnail((400, 400))
                img.save(ruta, format='WEBP', quality=80)
            except Exception as e:
                print(f"Error al redimensionar {nombre}: {e}")

# ✅ Limpia imágenes subidas por el usuario si el flujo se abandona o después de descargar
def limpiar_imagenes_usuario():
    carpeta = 'static/img/uploads'
    os.makedirs(carpeta, exist_ok=True)
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        try:
            if os.path.isfile(ruta):
                os.remove(ruta)
                print(f"Imagen eliminada: {nombre}")
        except Exception as e:
            print(f"Error al eliminar {nombre}: {e}")

@app.route('/', methods=['GET', 'POST'])
def step1():
    limpiar_imagenes_usuario()  # ✅ Limpieza si el usuario reinicia desde "/"
    if request.method == 'POST':
        session['tipo_web'] = 'catálogo'
        session['facebook'] = request.form.get('facebook')
        session['whatsapp'] = request.form.get('whatsapp')
        session['instagram'] = request.form.get('instagram')
        session['sobre_mi'] = request.form.get('sobre_mi')
        session['fuente'] = request.form.get('fuente')

        logo = request.files.get('logo')
        if logo:
            filename = secure_filename(logo.filename)
            if filename:
                logo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                session['logo'] = filename
        else:
            session['logo'] = None

        return redirect('/estilo')
    return render_template('step1.html')

@app.route('/estilo', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        session['color'] = request.form.get('color')
        session['estilo'] = request.form.get('estilo')
        session['bordes'] = request.form.get('bordes')
        session['botones'] = request.form.get('botones')
        session['vista_imagenes'] = request.form.get('vista_imagenes')
        session['estilo_visual'] = request.form.get('estilo_visual')

        return redirect('/contenido')

    imagenes = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('step2.html', config=session, imagenes=imagenes)

@app.route('/contenido', methods=['GET', 'POST'])
def step3():
    tipo = session.get('tipo_web')
    if request.method == 'POST':
        bloques = []

        nombres = request.form.getlist('nombre')
        descripciones = request.form.getlist('descripcion')
        precios = request.form.getlist('precio')
        grupos = request.form.getlist('grupo')
        imagenes = request.files.getlist('imagen')

        for i in range(len(nombres)):
            img = imagenes[i]
            filename = secure_filename(img.filename)
            if not filename:
                continue
            webp_name = os.path.splitext(filename)[0] + '.webp'
            destino = os.path.join(app.config['UPLOAD_FOLDER'], webp_name)
            convertir_y_comprimir(img, destino)
            bloques.append({
                'nombre': nombres[i],
                'descripcion': descripciones[i],
                'precio': precios[i],
                'imagen': webp_name,
                'grupo': grupos[i]
            })

        session['bloques'] = bloques
        return redirect('/preview')

    return render_template('step3.html', tipo_web=tipo)

@app.route('/preview')
def preview():
    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    config = {
        'tipo_web': session.get('tipo_web'),
        'color': session.get('color'),
        'fuente': session.get('fuente'),
        'estilo': session.get('estilo'),
        'bordes': session.get('bordes'),
        'botones': session.get('botones'),
        'vista_imagenes': session.get('vista_imagenes'),
        'logo': session.get('logo'),
        'estilo_visual': estilo_visual,
        'facebook': session.get('facebook'),
        'whatsapp': session.get('whatsapp'),
        'instagram': session.get('instagram'),
        'sobre_mi': session.get('sobre_mi'),
        'productos': session.get('bloques') if session.get('tipo_web') == 'catálogo' else [],
        'bloques': []
    }

    return render_template('preview.html', config=config)

@app.route('/descargar')
def descargar():
    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    config = {
        'tipo_web': session.get('tipo_web'),
        'color': session.get('color'),
        'fuente': session.get('fuente'),
        'estilo': session.get('estilo'),
        'bordes': session.get('bordes'),
        'botones': session.get('botones'),
        'vista_imagenes': session.get('vista_imagenes'),
        'logo': session.get('logo'),
        'estilo_visual': estilo_visual,
        'facebook': session.get('facebook'),
        'whatsapp': session.get('whatsapp'),
        'instagram': session.get('instagram'),
        'sobre_mi': session.get('sobre_mi'),
        'productos': session.get('bloques') if session.get('tipo_web') == 'catálogo' else [],
        'bloques': []
    }

    html = render_template('preview.html', config=config)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('index.html', html)

        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                zip_file.write(filepath, arcname='img/' + filename)

    limpiar_imagenes_usuario()  # ✅ Limpieza post-descarga

    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='sitio.zip')

if __name__ == '__main__':
    redimensionar_webp_en_static()
    limpiar_imagenes_usuario()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
