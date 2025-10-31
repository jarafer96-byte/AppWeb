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
import shortuuid  # ← ya la tenés instalada, ¿no?

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # 4 MB
app.secret_key = 'clave-secreta'

@app.errorhandler(413)
def too_large(e):
    return "Archivo demasiado grande (máx. 4 MB)", 413

# 🔥 Configuración de Firestore 
FIREBASE_PROJECT_ID = "hola1-4ed7f" 
FIREBASE_API_KEY = "AIzaSyDGqvK70SEKIYdabn1hM-EW9xHejcqYvGI" 
FIREBASE_COLLECTION = "productos"

# ✅ Actualización en subir_a_firestore
def subir_a_firestore(producto):
    url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents/{FIREBASE_COLLECTION}?key={FIREBASE_API_KEY}"
    headers = {"Content-Type": "application/json"}

    try:
        precio = int(producto["precio"])
        orden = int(producto.get("orden", 999))
    except ValueError:
        print(f"❌ Precio u orden inválido en producto: {producto['nombre']}")
        return False

    data = {
        "fields": {
            "nombre": {"stringValue": producto["nombre"]},
            "precio": {"integerValue": precio},
            "grupo": {"stringValue": producto["grupo"]},
            "subgrupo": {"stringValue": producto.get("subgrupo", "")},  # ✅ nuevo campo
            "descripcion": {"stringValue": producto.get("descripcion", "")},
            "imagen": {"stringValue": producto["imagen"]},
            "oferta": {"booleanValue": producto.get("oferta", False)},
            "orden": {"integerValue": orden}
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=5)
        if response.status_code in [200, 202]:
            return True
        else:
            print(f"❌ Error HTTP {response.status_code} al subir {producto['nombre']}")
            print(f"📄 Respuesta: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de red al subir {producto['nombre']}: {e}")
        return False


UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Compresión y redimensionado
def redimensionar_con_transparencia(imagen, destino, tamaño=(300, 180), calidad=80):
    try:
        img = Image.open(imagen.stream).convert('RGBA')
        img.thumbnail(tamaño, Image.LANCZOS)

        fondo = Image.new('RGBA', tamaño, (0, 0, 0, 0))  # fondo transparente
        offset = ((tamaño[0] - img.width) // 2, (tamaño[1] - img.height) // 2)
        fondo.paste(img, offset, img)  # usa la imagen como máscara

        fondo.save(destino, format='WEBP', quality=calidad)
    except Exception as e:
        print(f"Error al redimensionar con transparencia: {e}")

def necesita_redimension(src, dst):
    return not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)

def redimensionar_webp_en_static():
    carpeta = 'static/img/webp'
    os.makedirs(carpeta, exist_ok=True)
    for nombre in os.listdir(carpeta):
        if nombre.endswith('.webp'):
            ruta = os.path.join(carpeta, nombre)
            try:
                img = Image.open(ruta).convert('RGBA')
                tamaño = (300, 180)

                img.thumbnail(tamaño, Image.LANCZOS)
                fondo = Image.new('RGBA', tamaño, (0, 0, 0, 0))
                offset = ((tamaño[0] - img.width) // 2, (tamaño[1] - img.height) // 2)
                fondo.paste(img, offset, img)

                fondo.save(ruta, format='WEBP', quality=80)
                print(f"Redimensionado con transparencia: {nombre}")
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

# ... encabezado y configuraciones previas ...

@app.route('/contenido', methods=['GET', 'POST'])
def step3():
    tipo = session.get('tipo_web')
    if request.method == 'POST':
        bloques = []
        nombres = request.form.getlist('nombre')
        descripciones = request.form.getlist('descripcion')
        precios = request.form.getlist('precio')
        grupos = request.form.getlist('grupo')
        subgrupos = request.form.getlist('subgrupo')  # ✅ nuevo campo
        imagenes = request.files.getlist('imagen')
        ordenes = request.form.getlist('orden')

        longitudes = [len(nombres), len(precios), len(descripciones), len(grupos), len(subgrupos), len(imagenes), len(ordenes)]
        min_len = min(longitudes)
        print("🧪 Longitudes:", longitudes)

        if not all(l == min_len for l in longitudes):
            print("❌ Desalineación en los datos del formulario")
            return "Error: los campos del formulario están desalineados", 500

        MAX_SIZE_MB = 4
        formatos_validos = ('.jpg', '.jpeg', '.png', '.webp')

        for i in range(len(nombres)):
            nombre = nombres[i].strip()
            precio = precios[i].strip()
            grupo = grupos[i].strip() or 'Sin grupo'
            subgrupo = subgrupos[i].strip() or 'Sin subgrupo'
            orden = ordenes[i].strip() if i < len(ordenes) else '999'
            img = imagenes[i]
            filename = secure_filename(img.filename)

            if not nombre or not precio or not grupo or not subgrupo or not filename:
                continue

            if not filename.lower().endswith(formatos_validos):
                print(f"⚠️ Formato no soportado: {filename}")
                continue

            if img.content_length and img.content_length > MAX_SIZE_MB * 1024 * 1024:
                print(f"⚠️ Imagen demasiado pesada: {filename}")
                continue

            webp_name = f"{os.path.splitext(filename)[0]}_{shortuuid.uuid()[:4]}.webp"
            destino = os.path.join(app.config['UPLOAD_FOLDER'], webp_name)

            try:
                img.save(destino)
            except Exception as e:
                print(f"❌ Error al guardar imagen {filename}: {e}")
                continue

            bloques.append({
                'nombre': nombre,
                'descripcion': descripciones[i],
                'precio': precio,
                'imagen': webp_name,
                'grupo': grupo,
                'subgrupo': subgrupo,  # ✅ incluir subgrupo
                'orden': ordenes[i]
            })

        session['bloques'] = bloques
        exitos = 0
        fallos = 0

        def subir_con_resultado(producto):
            try:
                if subir_a_firestore(producto):
                    print(f"✅ Producto subido: {producto['nombre']}")
                    return True
                else:
                    print(f"⚠️ Fallo al subir {producto['nombre']}")
                    return False
            except Exception as e:
                print(f"❌ Error inesperado al subir {producto['nombre']}: {e}")
                return False

        bloques_por_lote = 10
        try:
            for inicio in range(0, len(bloques), bloques_por_lote):
                lote = bloques[inicio:inicio + bloques_por_lote]
                with ThreadPoolExecutor(max_workers=5) as executor:
                    resultados = list(executor.map(subir_con_resultado, lote))
                    exitos += sum(resultados)
                    fallos += len(resultados) - sum(resultados)
        except Exception as lote_error:
            print(f"🔥 Error crítico en lote de subida: {lote_error}")

        print(f"🧮 Subidos correctamente: {exitos} / Fallidos: {fallos}")

        if exitos > 0:
            return redirect('/preview')
        else:
            return render_template('step3.html', tipo_web=tipo)

    return render_template('step3.html', tipo_web=tipo)

@app.route('/preview')
def preview():
    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    config = {
        'titulo': session.get('titulo'),
        'descripcion': session.get('descripcion'),
        'imagen_destacada': session.get('imagen_destacada'),
        'url': session.get('url'),
        'nombre_emprendimiento': session.get('nombre_emprendimiento'),
        'anio': session.get('anio'),
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
        'bloques': [],
        'descargado': session.get('descargado', False),
        'usarFirestore': True
    }

    for i, p in enumerate(config['productos']):
        p['id_base'] = p['nombre'].replace(' ', '_') + f"_{i}"

    # ✅ Agrupar por grupo y subgrupo
    grupos_dict = {}
    for producto in config['productos']:
        grupo = producto.get('grupo') or producto.get('Grupo') or 'General'
        subgrupo = producto.get('subgrupo') or producto.get('subGrupo') or 'Sin subgrupo'

        grupo = grupo.strip().title()
        subgrupo = subgrupo.strip().title()

        if grupo not in grupos_dict:
            grupos_dict[grupo] = {}
        if subgrupo not in grupos_dict[grupo]:
            grupos_dict[grupo][subgrupo] = []
        grupos_dict[grupo][subgrupo].append(producto)

    config['usarFirestore'] = False  # o False según lo que quieras

    return render_template('preview.html', config=config, grupos=grupos_dict)


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

    # ✅ Construir grupos y subgrupos con validación y normalización
    grupos = {}
    for producto in config['productos']:
        grupo = producto.get('grupo') or producto.get('Grupo') or 'General'
        subgrupo = producto.get('subgrupo') or producto.get('subGrupo') or 'Sin subgrupo'

        grupo = grupo.strip().title()
        subgrupo = subgrupo.strip().title()

        if grupo not in grupos:
            grupos[grupo] = {}
        if subgrupo not in grupos[grupo]:
            grupos[grupo][subgrupo] = []
        grupos[grupo][subgrupo].append(producto)

    # ✅ Renderizar HTML con grupos incluidos
    html = render_template('preview.html', config=config, grupos=grupos)

    # ✅ Crear ZIP con HTML y recursos
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('index.html', html)

        # ✅ Incluir fondo visual
        fondo = f"{estilo_visual}.jpeg"
        fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
        if os.path.exists(fondo_path):
            zip_file.write(fondo_path, arcname='img/' + fondo)

        # ✅ Incluir imágenes de productos
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
