from flask import Flask, render_template, request, redirect, session, send_file, url_for
import os
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from io import BytesIO
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import json

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # 4 MB
app.secret_key = 'clave-secreta'

@app.errorhandler(413)
def too_large(e):
    return "Archivo demasiado grande (máx. 4 MB)", 413

# 🔥 Configuración de Firestore 
FIREBASE_PROJECT_ID = "appweb-2167a" 
FIREBASE_API_KEY = "AIzaSyALJLWb4tPUVq9UwZ9dB-L6P1AJX9TWCeM" 
FIREBASE_COLLECTION = "productos"

def subir_a_firestore(producto):
    url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/{FIREBASE_COLLECTION}?key={FIREBASE_API_KEY}"
    headers = {"Content-Type": "application/json"}

    data = {
        "fields": {
            "nombre": {"stringValue": producto["nombre"]},
            "precio": {"integerValue": int(producto["precio"])},
            "grupo": {"stringValue": producto["grupo"]},
            "descripcion": {"stringValue": producto.get("descripcion", "")},
            "imagen": {"stringValue": producto["imagen"]},
            "oferta": {"booleanValue": producto.get("oferta", False)}
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.status_code == 200 or response.status_code == 202


UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Compresión y redimensionado
def convertir_y_comprimir(imagen, destino, calidad=70, max_size=(300, 300)):
    try:
        img = Image.open(imagen.stream)
        img = img.convert('RGB')
        img.thumbnail(max_size)
        img.save(destino, format='WEBP', quality=calidad)
    except Exception as e:
        print(f"Error al comprimir imagen: {e}")

def necesita_redimension(src, dst):
    return not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)

def redimensionar_webp_en_static():
    carpeta = 'static/img/webp'
    os.makedirs(carpeta, exist_ok=True)
    for nombre in os.listdir(carpeta):
        if nombre.endswith('.webp'):
            ruta = os.path.join(carpeta, nombre)
            try:
                img = Image.open(ruta)
                img = img.convert('RGB')
                # Solo redimensionar si es mayor a 400x400
                if img.width > 400 or img.height > 400:
                    img.thumbnail((400, 400))
                    img.save(ruta, format='WEBP', quality=80)
                    print(f"Redimensionado: {nombre}")
                else:
                    print(f"Sin cambios: {nombre}")
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
    limpiar_imagenes_usuario()
    if request.method == 'POST':
        session['tipo_web'] = 'catálogo'
        session['facebook'] = request.form.get('facebook')
        session['whatsapp'] = request.form.get('whatsapp')
        session['instagram'] = request.form.get('instagram')
        session['sobre_mi'] = request.form.get('sobre_mi')
        session['ubicacion'] = request.form.get('ubicacion')
        session['link_mapa'] = request.form.get('link_mapa')
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

    imagenes = os.listdir('static/img/webp')
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

        tareas = []
        max_workers = min(4, len(imagenes))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(len(nombres)):
                nombre = nombres[i].strip()
                precio = precios[i].strip()
                grupo = grupos[i].strip()
                img = imagenes[i]
                filename = secure_filename(img.filename)

                if not nombre or not precio or not grupo or not filename:
                    continue

                webp_name = os.path.splitext(filename)[0] + '.webp'
                destino = os.path.join(app.config['UPLOAD_FOLDER'], webp_name)

                src_temp = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                img.save(src_temp)  # guardar temporalmente para comparar fechas

                if necesita_redimension(src_temp, destino):
                    tareas.append(executor.submit(convertir_y_comprimir, img, destino))
                else:
                    print(f"Usando caché existente: {webp_name}")
                if os.path.exists(src_temp):
                    os.remove(src_temp)


                bloques.append({
                    'nombre': nombre,
                    'descripcion': descripciones[i],
                    'precio': precio,
                    'imagen': webp_name,
                    'grupo': grupo
                })

        session['bloques'] = bloques
        for producto in bloques:
            subir_a_firestore(producto)

        return redirect('/preview')

    return render_template('step3.html', tipo_web=tipo)

@app.route('/preview')
def preview():
    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    config = {
        'tipo_web': session.get('tipo_web'),
        'ubicacion': session.get('ubicacion'),
        'link_mapa': session.get('link_mapa'),
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
        'ubicacion': session.get('ubicacion'),
        'link_mapa': session.get('link_mapa'),
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

    limpiar_imagenes_usuario()

    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='sitio.zip')

@app.after_request
def cache(response):
    if request.path.startswith("/static/img"):
        response.headers["Cache-Control"] = "public, max-age=31536000"
    return response

if __name__ == '__main__':
    redimensionar_webp_en_static()
    limpiar_imagenes_usuario()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
