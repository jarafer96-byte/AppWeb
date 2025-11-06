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
import shortuuid
import firebase_admin
from firebase_admin import credentials, firestore
import tempfile

if not firebase_admin._apps:
    cred_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if cred_json:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as f:
            f.write(cred_json)
            cred_path = f.name
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        raise RuntimeError("❌ Falta la variable GOOGLE_APPLICATION_CREDENTIALS_JSON")

db = firestore.client()  # ✅ solo una vez, después de inicializar


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # 4 MB
app.config['UPLOAD_FOLDER'] = 'static/img'
app.secret_key = 'clave-secreta'

@app.errorhandler(413)
def too_large(e):
    return "Archivo demasiado grande (máx. 4 MB)", 413

# 🔥 Configuración de Firestore 
FIREBASE_PROJECT_ID = "appweb-2167a" 
FIREBASE_API_KEY = "AIzaSyALJLWb4tPUVq9UwZ9dB-L6P1AJX9TWCeM" 
FIREBASE_COLLECTION = "productos"

# ✅ Actualización en subir_a_firestore
def subir_a_firestore(producto):
    grupo_original = producto["grupo"].strip()
    subgrupo_original = producto.get("subgrupo", "general").strip()
    nombre_original = producto["nombre"].strip()

    # Normalización solo para el ID
    grupo_id = grupo_original.replace(" ", "_").lower()
    nombre_id = nombre_original.replace(" ", "_").lower()
    fecha = time.strftime("%Y%m%d")
    custom_id = f"{nombre_id}_{fecha}_{grupo_id}"

    # URL con ID personalizado
    doc_path = f"projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/{FIREBASE_COLLECTION}/{custom_id}"
    url = f"https://firestore.googleapis.com/v1/{doc_path}?key={FIREBASE_API_KEY}"
    headers = {"Content-Type": "application/json"}

    try:
        data = {
            "fields": {
                "nombre": {"stringValue": nombre_original},
                "descripcion": {"stringValue": producto.get("descripcion", "")},
                "precio": {"doubleValue": float(producto.get("precio", 0))},
                "imagen": {"stringValue": producto.get("imagen", "")},
                "grupo": {"stringValue": grupo_original},
                "subgrupo": {"stringValue": subgrupo_original},
                "talles": {"arrayValue": {"values": [{"stringValue": t} for t in producto.get("talles", [])]}}
            }
        }
        response = requests.patch(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return custom_id
    except requests.exceptions.RequestException as e:
        print(f"Error al subir a Firestore: {e}")
        return None

def redimensionar_webp_en_static():
    carpeta = app.config['UPLOAD_FOLDER']
    for archivo in os.listdir(carpeta):
        if archivo.lower().endswith('.webp'):
            ruta = os.path.join(carpeta, archivo)
            try:
                with Image.open(ruta) as img:
                    if img.size[0] > 300 or img.size[1] > 300:
                        img.thumbnail((300, 300))
                        img.save(ruta, 'WEBP')
            except Exception as e:
                print(f"Error al redimensionar {archivo}: {e}")

def limpiar_imagenes_usuario():
    carpeta = app.config['UPLOAD_FOLDER']
    for archivo in os.listdir(carpeta):
        if archivo.startswith('user_') and archivo.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            os.remove(os.path.join(carpeta, archivo))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        config = {
            'titulo': request.form.get('titulo', 'Mi Tienda'),
            'descripcion': request.form.get('descripcion', 'Descripción por defecto'),
            'imagen_destacada': request.form.get('imagen_destacada', 'default.jpg'),
            'url': request.form.get('url', 'https://example.com'),
            'whatsapp': request.form.get('whatsapp', '#'),
            'facebook': request.form.get('facebook', '#'),
            'instagram': request.form.get('instagram', '#'),
            'maps': request.form.get('maps', '#'),
            'direccion': request.form.get('direccion', 'Dirección no especificada'),
            'logo': request.form.get('logo', 'mini_1_jfjf8.jpeg'),
            'fuente': request.form.get('fuente', 'Raleway'),
            'color': request.form.get('color', '#ff6f61'),
            'estilo_visual': request.form.get('estilo_visual', 'oscuro'),
            'productos': []
        }

        if 'imagen' in request.files:
            archivo = request.files['imagen']
            if archivo and archivo.filename:
                filename = secure_filename(f"user_{shortuuid.uuid()}.{archivo.filename.rsplit('.', 1)[1].lower()}")
                ruta = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                archivo.save(ruta)
                config['imagen_destacada'] = filename

        productos = []
        for i in range(1, 11):  # Suponemos hasta 10 productos
            nombre = request.form.get(f'nombre_{i}')
            if nombre:
                producto = {
                    'nombre': nombre,
                    'descripcion': request.form.get(f'descripcion_{i}', ''),
                    'precio': request.form.get(f'precio_{i}', '0'),
                    'imagen': request.form.get(f'imagen_{i}', ''),
                    'grupo': request.form.get(f'grupo_{i}', 'General'),
                    'subgrupo': request.form.get(f'subgrupo_{i}', 'General'),
                    'talles': request.form.getlist(f'talles_{i}') if request.form.get(f'talles_{i}') else []
                }
                if 'imagen_producto_' + str(i) in request.files:
                    archivo = request.files['imagen_producto_' + str(i)]
                    if archivo and archivo.filename:
                        filename = secure_filename(f"user_{shortuuid.uuid()}.{archivo.filename.rsplit('.', 1)[1].lower()}")
                        ruta = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        archivo.save(ruta)
                        producto['imagen'] = filename
                productos.append(producto)
                subir_a_firestore(producto)  # Subir cada producto a Firestore

        config['productos'] = productos
        session['config'] = config

        grupos = {}
        for producto in config['productos']:
            grupo = producto.get('grupo', 'General')
            subgrupo = producto.get('subgrupo', 'General')
            if grupo not in grupos:
                grupos[grupo] = {}
            if subgrupo not in grupos[grupo]:
                grupos[grupo][subgrupo] = []
            grupos[grupo][subgrupo].append(producto)

        return render_template('preview.html', config=config, grupos=grupos, modoAdmin=True)

    return render_template('index.html')

@app.route('/preview')
def preview():
    config = session.get('config', {
        'titulo': 'Mi Tienda',
        'descripcion': 'Descripción por defecto',
        'imagen_destacada': 'default.jpg',
        'url': 'https://example.com',
        'whatsapp': '#',
        'facebook': '#',
        'instagram': '#',
        'maps': '#',
        'direccion': 'Dirección no especificada',
        'logo': 'mini_1_jfjf8.jpeg',
        'fuente': 'Raleway',
        'color': '#ff6f61',
        'estilo_visual': 'oscuro',
        'productos': []
    })
    grupos = {}
    for producto in config['productos']:
        grupo = producto.get('grupo', 'General')
        subgrupo = producto.get('subgrupo', 'General')
        if grupo not in grupos:
            grupos[grupo] = {}
        if subgrupo not in grupos[grupo]:
            grupos[grupo][subgrupo] = []
        grupos[grupo][subgrupo].append(producto)

    html = render_template('preview.html', config=config, grupos=grupos, modoAdmin=True)
    return html

@app.route('/download')
def download():
    config = session.get('config', {
        'titulo': 'Mi Tienda',
        'descripcion': 'Descripción por defecto',
        'imagen_destacada': 'default.jpg',
        'url': 'https://example.com',
        'whatsapp': '#',
        'facebook': '#',
        'instagram': '#',
        'maps': '#',
        'direccion': 'Dirección no especificada',
        'logo': 'mini_1_jfjf8.jpeg',
        'fuente': 'Raleway',
        'color': '#ff6f61',
        'estilo_visual': 'oscuro',
        'productos': []
    })
    estilo_visual = config.get('estilo_visual', 'oscuro')

    grupos = {}
    for producto in config['productos']:
        grupo = producto.get('grupo', 'General')
        subgrupo = producto.get('subgrupo', 'General')
        if grupo not in grupos:
            grupos[grupo] = {}
        if subgrupo not in grupos[grupo]:
            grupos[grupo][subgrupo] = []
        grupos[grupo][subgrupo].append(producto)

    html = render_template('preview.html', config=config, grupos=grupos)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('index.html', html)

        fondo = f"{estilo_visual}.jpeg"
        fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
        if os.path.exists(fondo_path):
            zip_file.write(fondo_path, arcname='img/' + fondo)

        for producto in config['productos']:
            imagen = producto.get('imagen')
            if imagen:
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen)
                if os.path.exists(imagen_path):
                    zip_file.write(imagen_path, arcname='img/' + imagen)

    limpiar_imagenes_usuario()
    session['descargado'] = True

    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='sitio.zip')

@app.template_filter('imgver')
def imgver_filter(name):
    try:
        return int(os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], name))) % 10_000
    except Exception:
        return 0
        
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
