from flask import Flask, render_template, redirect, session, send_file, url_for, jsonify, current_app, request, flash
import requests
import os
import uuid
import re
import time
import json
import gc
import pandas as pd
import boto3
import traceback
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from io import BytesIO
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import shortuuid
import mercadopago
import base64
import firebase_admin
from firebase_admin import credentials, firestore
# 🔐 Inicialización segura de Firebase
try:
    cred_dict = json.loads(os.getenv("FIREBASE_CREDENTIALS_JSON"))
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase inicializado con:", firebase_admin.get_app().name)
except Exception as e:
    print("❌ Error al cargar JSON:", e)

# Cliente Firestore con acceso total
db = firestore.client()

s3 = boto3.client(
    's3',
    endpoint_url='https://s3.us-east-005.backblazeb2.com',
    aws_access_key_id=os.getenv('ACCESS_KEY'),
    aws_secret_access_key=os.getenv('SECRET_KEY')
)
BUCKET = os.getenv('BUCKET') or 'imagenes-appweb'

# 🔑 Inicialización segura de Mercado Pago
access_token = os.getenv("MERCADO_PAGO_TOKEN")
if access_token and isinstance(access_token, str):
    sdk = mercadopago.SDK(access_token.strip())
    print("✅ SDK de Mercado Pago inicializado globalmente")
else:
    sdk = None
    print("⚠️ MERCADO_PAGO_TOKEN no configurado, SDK no inicializado")
# GitHub y Flask config
token = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "jarafer96-byte"

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 4 MB
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "clave-secreta-temporal"
app.config['SESSION_COOKIE_SECURE'] = not app.debug

@app.errorhandler(413)
def too_large(e):
    return "Archivo demasiado grande (máx. 200 MB)", 413

firebase_config = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
}

UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def subir_a_firestore(producto, email):
    if not producto.get("nombre") or not producto.get("grupo") or not producto.get("precio"):
        return False

    grupo_original = producto["grupo"].strip()
    subgrupo_original = producto.get("subgrupo", "general").strip()
    nombre_original = producto["nombre"].strip()

    grupo_id = grupo_original.replace(" ", "_").lower()
    nombre_id = nombre_original.replace(" ", "_").lower()
    fecha = time.strftime("%Y%m%d")

    sufijo = uuid.uuid4().hex[:6]
    custom_id = f"{nombre_id}_{fecha}_{grupo_id}_{sufijo}"

    try:
        precio = int(producto["precio"].replace("$", "").replace(".", "").strip())
        orden = int(producto.get("orden", 999))
    except ValueError:
        return False

    talles = producto.get("talles") or []
    if isinstance(talles, str):
        talles = [t.strip() for t in talles.split(',') if t.strip()]

    try:
        producto["id_base"] = custom_id

        doc = {
            "nombre": nombre_original,
            "id_base": custom_id,
            "precio": precio,
            "grupo": grupo_original,
            "subgrupo": subgrupo_original,
            "descripcion": producto.get("descripcion", ""),
            "imagen_backblaze": producto.get("imagen_backblaze"),
            "imagen_github": producto.get("imagen_github"),
            "orden": orden,
            "talles": talles,
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        db.collection("usuarios").document(email).collection("productos").document(custom_id).set(doc)
        return True
    except Exception:
        return False

def subir_archivo(repo, contenido_bytes, ruta_remota, token, branch="main"):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo}/contents/{ruta_remota}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Obtener SHA si el archivo ya existe
    sha = None
    try:
        r_get = requests.get(url, headers=headers, timeout=10)
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")
    except Exception:
        sha = None

    data = {
        "message": f"Actualización automática de {ruta_remota}",
        "content": base64.b64encode(contenido_bytes).decode("utf-8"),
        "branch": branch
    }
    if sha:
        data["sha"] = sha  # necesario para actualizar

    try:
        r = requests.put(url, headers=headers, json=data, timeout=10)
        if r.status_code in (200, 201):
            return {
                "ok": True,
                "url": r.json().get("content", {}).get("html_url"),
                "status": r.status_code
            }
        else:
            return {"ok": False, "status": r.status_code, "error": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def subir_iconos_png(repo, token):
    carpeta = os.path.join("static", "img")
    for nombre_archivo in os.listdir(carpeta):
        if nombre_archivo.lower().endswith(".png"):
            ruta_local = os.path.join(carpeta, nombre_archivo)
            ruta_remota = f"static/img/{nombre_archivo}"
            with open(ruta_local, "rb") as f:
                contenido = f.read()
            subir_archivo(repo, contenido, ruta_remota, token)

def generar_nombre_repo(email):
    base = email.replace("@", "_at_").replace(".", "_")
    fecha = time.strftime("%Y%m%d")
    return f"{base}_{fecha}"


def guardar_redimensionada(file, nombre_archivo):
    ruta_tmp = os.path.join("/tmp", nombre_archivo)
    img = Image.open(file)
    img.thumbnail((800, 800))  # ejemplo de redimensión
    img.save(ruta_tmp, "WEBP")
    return ruta_tmp

def crear_repo_github(nombre_repo, token):
    if not token:
        return {"error": "Token no disponible"}

    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "name": nombre_repo,
        "private": False,
        "auto_init": True,
        "description": "Repositorio generado automáticamente desde step1"
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 201:
            repo_url = response.json().get("html_url", "URL no disponible")
            return {"url": repo_url}
        else:
            return {"error": response.text}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def limpiar_imagenes_usuario():
    carpeta = 'static/img/uploads'
    os.makedirs(carpeta, exist_ok=True)
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        try:
            if os.path.isfile(ruta):
                os.remove(ruta)
        except Exception:
            pass

def redimensionar_y_subir(imagen, email):
    try:
        pil = Image.open(imagen).convert("RGBA")

        target_size = (300, 200)
        img_ratio = pil.width / pil.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)

        pil = pil.resize((new_width, new_height), Image.LANCZOS)

        fondo = Image.new("RGBA", target_size, (0, 0, 0, 0))
        offset = ((target_size[0] - new_width) // 2, (target_size[1] - new_height) // 2)
        fondo.paste(pil, offset, pil)

        buffer = BytesIO()
        fondo.save(buffer, format="WEBP", quality=80)
        buffer.seek(0)

        nombre = f"mini_{uuid.uuid4().hex}.webp"
        ruta_s3 = f"usuarios/{email}/{nombre}"

        ruta_tmp = os.path.join("/tmp", nombre)
        with open(ruta_tmp, "wb") as f:
            f.write(buffer.getvalue())

        s3.upload_fileobj(buffer, BUCKET, ruta_s3, ExtraArgs={'ContentType': 'image/webp'})
        url_final = f"https://{BUCKET}.s3.us-west-004.backblazeb2.com/{ruta_s3}"
        return url_final
    except Exception:
        return None

def normalizar_url(url: str) -> str:
    if "/file/imagenes-appweb/" in url:
        return url.split("/file/imagenes-appweb/")[1]
    elif "s3.us-west-004.backblazeb2.com" in url or "s3.us-east-005.backblazeb2.com" in url:
        if "/usuarios/" in url:
            return "usuarios/" + url.split("/usuarios/")[1]
    return url

@app.route('/step0', methods=['GET', 'POST'])
def step0():
    if request.method == 'POST':
        email = session.get('email', 'anonimo')
        imagenes = request.files.getlist('imagenes')

        if not imagenes:
            return "No se recibieron imágenes", 400

        if 'imagenes_step0' not in session:
            session['imagenes_step0'] = []

        if len(session['imagenes_step0']) + len(imagenes) > 120:
            return "Límite de imágenes alcanzado", 400

        def chunks(lista, n):
            for i in range(0, len(lista), n):
                yield lista[i:i+n]

        urls = []
        for lote in chunks([img for img in imagenes if img and img.filename], 40):
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(redimensionar_y_subir, img, email) for img in lote]
                for f in futures:
                    url = f.result()
                    if url:
                        urls.append(normalizar_url(url))

        session['imagenes_step0'].extend(urls)
        return redirect('/estilo')

    return render_template('step0.html')

def get_mp_token(email: str):
    """Obtiene el access_token de Mercado Pago desde Firestore o Render, con fallback a refresh_token."""
    try:
        if email:
            doc_ref = db.collection("usuarios").document(email).collection("config").document("mercado_pago")
            snap = doc_ref.get()
            if snap.exists:
                data = snap.to_dict()
                token = data.get("access_token")
                if token and isinstance(token, str) and token.strip():
                    return token.strip()

                # Fallback: intentar refrescar con refresh_token
                refresh_token = data.get("refresh_token")
                if refresh_token:
                    client_id = os.getenv("MP_CLIENT_ID")
                    client_secret = os.getenv("MP_CLIENT_SECRET")
                    token_url = "https://api.mercadopago.com/oauth/token"
                    payload = {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                    try:
                        resp = requests.post(token_url, data=payload, timeout=10)
                        if resp.status_code == 200:
                            new_data = resp.json()
                            new_token = new_data.get("access_token")
                            if new_token:
                                # Guardar el nuevo token en Firestore
                                doc_ref.set({"access_token": new_token}, merge=True)
                                print("[MP-HELPER] ✅ Token refrescado y guardado")
                                return new_token.strip()
                    except Exception as e:
                        print(f"[MP-HELPER] Error refrescando token: {e}")
    except Exception as e:
        print("❌ Error al leer token de Firestore:", e)

    # Fallback global
    token = os.getenv("MERCADO_PAGO_TOKEN")
    if token and isinstance(token, str):
        return token.strip()

    return None

# Rutas de retorno (back_urls)
@app.route('/success')
def pago_success():
    return "✅ Pago aprobado correctamente. ¡Gracias por tu compra!"

@app.route('/failure')
def pago_failure():
    return "❌ El pago fue rechazado o falló."

@app.route('/pending')
def pago_pending():
    return "⏳ El pago está pendiente de aprobación."

@app.route("/webhook_mp", methods=["POST"])
def webhook_mp():
    event = request.json or {}
    # ✅ Registrar el evento crudo para auditoría (opcional)
    log_event("mp_webhook", event)

    # Podés inspeccionar si querés ver qué llega
    topic = event.get("type") or event.get("action")
    payment_id = event.get("data", {}).get("id")

    if topic == "payment" and payment_id:
        try:
            # Consultar detalle del pago solo para auditar (opcional)
            detail = requests.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {get_platform_token()}"}
            ).json()
            log_event("mp_payment_detail", detail)
        except Exception as e:
            log_event("mp_webhook_error", str(e))

    # ✅ No se guarda nada en Firestore, solo respondemos OK
    return "OK", 200

@app.route("/test-firestore")
def test_firestore():
    try:
        db.collection("test").document("ping").set({"ok": True})
        return "✅ Firestore funciona"
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error: {e}", 500

@app.route('/crear-admin', methods=['POST'])
def crear_admin():
    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario')
    clave = data.get('clave')

    if not usuario or not clave:
        return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

    try:
        session.clear()
        session['email'] = usuario
        session['modo_admin'] = True

        doc_ref = db.collection("usuarios").document(usuario)
        doc_ref.set({
            "clave_admin": clave
        })
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/debug/mp')
def debug_mp():
    email = session.get('email')
    if not email:
        return jsonify({'error': 'sin sesión'}), 400

    try:
        doc = db.collection("usuarios").document(email).collection("config").document("mercado_pago").get()
        if doc.exists:
            data = doc.to_dict() or {}
            # 🔎 Filtrar campos sensibles si no querés exponerlos en frontend
            safe_data = {
                "public_key": data.get("public_key"),
                "access_token": bool(data.get("access_token")),  # solo indicar si existe
                "refresh_token": bool(data.get("refresh_token")),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "live_mode": data.get("live_mode"),
                "scope": data.get("scope"),
                "user_id": data.get("user_id"),
            }
            return jsonify(safe_data)
        else:
            return jsonify({'error': 'no encontrado'}), 404
    except Exception as e:
        print(f"[DEBUG-MP] Error leyendo Firestore: {e}")
        return jsonify({'error': 'Error interno', 'message': str(e)}), 500

@app.route('/login-admin', methods=['POST'])
def login_admin():
    session.clear()

    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario')
    clave_ingresada = data.get('clave')

    if not usuario or not clave_ingresada:
        return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", usuario):
        return jsonify({'status': 'error', 'message': 'El usuario debe tener formato de email'}), 400

    try:
        doc_ref = db.collection("usuarios").document(usuario)
        doc = doc_ref.get()

        if not doc.exists:
            return jsonify({'status': 'error', 'message': 'Usuario no registrado'}), 404

        clave_guardada = doc.to_dict().get("clave_admin")

        if clave_guardada == clave_ingresada:
            session.permanent = True
            session['modo_admin'] = True
            session['email'] = usuario
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'status': 'error', 'message': 'Clave incorrecta'}), 403

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/logout-admin')
def logout_admin():
    session.pop('modo_admin', None)
    return redirect('/preview')

@app.route('/guardar-producto', methods=['POST'])
def guardar_producto():
    usuario = session.get('email')
    if not usuario:
        return jsonify({'status': 'error', 'message': 'No estás logueado'}), 403

    data = request.get_json(silent=True) or {}
    producto = data.get('producto')

    if not producto:
        return jsonify({'status': 'error', 'message': 'Producto inválido'}), 400

    try:
        ruta = f"usuarios/{usuario}/productos"
        db.collection(ruta).add(producto)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/ver-productos')
def ver_productos():
    usuario = session.get('email')
    if not usuario:
        return jsonify([])

    try:
        ruta = f"usuarios/{usuario}/productos"
        docs = db.collection(ruta).get()
        productos = [doc.to_dict() for doc in docs]
        return jsonify(productos)
    except Exception:
        return jsonify([])


@app.route("/crear-repo", methods=["POST"])
def crear_repo():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return jsonify({"error": "Token no disponible"}), 500

    email = request.json.get("email", f"repo-{uuid.uuid4().hex[:6]}")
    session['email'] = email
    nombre_repo = generar_nombre_repo(email)
    session['repo_nombre'] = nombre_repo

    resultado = crear_repo_github(nombre_repo, token)
    if "url" in resultado:
        session['repo_creado'] = resultado["url"]

    return jsonify(resultado), 200 if "url" in resultado else 400

@app.route('/actualizar-precio', methods=['POST'])
def actualizar_precio():
    data = request.get_json()
    id_base = data.get("id")
    nuevo_precio_raw = data.get("nuevoPrecio", 0)
    email = session.get("email")

    if not email or not id_base:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        nuevo_precio = int(nuevo_precio_raw)
    except ValueError:
        return jsonify({"error": "Precio inválido"}), 400

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            return jsonify({"error": "Producto no encontrado"}), 404

        doc = query[0]
        doc.reference.update({"precio": nuevo_precio})
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/actualizar-talles', methods=['POST'])
def actualizar_talles():
    data = request.get_json()
    id_base = data.get("id")
    nuevos_talles = data.get("talles", [])
    email = session.get("email")

    if not email or not id_base:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        db.collection("usuarios").document(email).collection("productos").document(id_base).update({
            "talles": nuevos_talles
        })
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/actualizar-firestore', methods=['POST'])
def actualizar_firestore():
    data = request.get_json(silent=True) or {}
    id_base = data.get('id')
    campos = {k: v for k, v in data.items() if k != 'id'}
    email = session.get("email")

    if not email or not id_base or not campos:
        return jsonify({'status': 'error', 'message': 'Datos incompletos'}), 400

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            return jsonify({'status': 'error', 'message': 'Producto no encontrado'}), 404

        doc = query[0]
        doc.reference.update(campos)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

        mercado_pago = request.form.get('mercado_pago')
        if mercado_pago and mercado_pago.startswith("APP_USR-"):
            session['mercado_pago'] = mercado_pago.strip()
        else:
            session.pop('mercado_pago', None)

        logo = request.files.get('logo')
        if logo:
            filename = secure_filename(logo.filename)
            if filename:
                logo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                session['logo'] = filename
        else:
            session['logo'] = None

        return redirect('/step0')

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

        return redirect('/step2-5')
        
    imagenes = os.listdir('static/img/webp')
    return render_template('step2.html', config=session, imagenes=imagenes)
    
@app.route('/step2-5', methods=['GET','POST'])
def step2_5():
    if request.method == 'POST':
        filas = []
        for key in request.form:
            if key.startswith("grupo_"):
                idx = key.split("_")[1]
                grupo = request.form.get(f"grupo_{idx}", "").strip()
                subgrupo = request.form.get(f"subgrupo_{idx}", "").strip()
                cantidad = int(request.form.get(f"filas_{idx}", "0"))
                talles = request.form.get(f"talles_{idx}", "").strip()  # ✅ nuevo campo

                if grupo and subgrupo and cantidad > 0:
                    for n in range(1, cantidad+1):
                        filas.append({
                            "Grupo": grupo,
                            "Subgrupo": subgrupo,
                            "Producto": f"{subgrupo}{n}",
                            "Talles": talles
                        })

        # Crear Excel en memoria
        df = pd.DataFrame(filas, columns=["Grupo","Subgrupo","Producto","Talles"])
        output = BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="productos.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return render_template('step2-5.html')


@app.route('/contenido', methods=['GET', 'POST'])
def step3():
    tipo = session.get('tipo_web')
    email = session.get('email')
    imagenes_session = session.get('imagenes_step0') or []

    imagenes_disponibles = [
        f"https://f005.backblazeb2.com/file/imagenes-appweb/{img}"
        for img in imagenes_session
    ]

    if not email:
        return "Error: sesión no iniciada", 403

    if request.method == 'POST':
        bloques = []
        nombres = request.form.getlist('nombre')
        descripciones = request.form.getlist('descripcion')
        precios = request.form.getlist('precio')
        grupos = request.form.getlist('grupo')
        subgrupos = request.form.getlist('subgrupo')
        ordenes = request.form.getlist('orden')
        talles = request.form.getlist('talles')
        imagenes_elegidas = request.form.getlist('imagen_elegida')
        imagenes_basename = request.form.getlist('imagen_basename')

        repo_name = session.get('repo_nombre') or "AppWeb"
        github_token = os.getenv("GITHUB_TOKEN")

        for i in range(len(nombres)):
            nombre = nombres[i].strip()
            precio = precios[i].strip()
            grupo = grupos[i].strip() or 'Sin grupo'
            subgrupo = subgrupos[i].strip() or 'Sin subgrupo'
            orden = ordenes[i].strip() or str(i + 1)

            imagen_url = imagenes_elegidas[i].strip() if i < len(imagenes_elegidas) else ''
            imagen_base = imagenes_basename[i].strip() if i < len(imagenes_basename) else ''

            if not imagen_url or not nombre or not precio or not grupo or not subgrupo:
                continue

            talle_raw = talles[i].strip() if i < len(talles) else ''
            talle_lista = [t.strip() for t in talle_raw.split(',') if t.strip()]

            url_backblaze = imagen_url
            ruta_tmp = os.path.join("/tmp", imagen_base)
            if os.path.exists(ruta_tmp) and github_token:
                try:
                    with open(ruta_tmp, "rb") as f:
                        contenido_bytes = f.read()
                    resultado_github = subir_archivo(
                        repo_name,
                        contenido_bytes,
                        f"static/img/{imagen_base}",
                        github_token
                    )
                    url_github = f"/static/img/{imagen_base}" if resultado_github.get("ok") else ""
                    del contenido_bytes
                    gc.collect()
                except Exception:
                    url_github = ""
            else:
                url_github = ""

            bloques.append({
                'nombre': nombre,
                'descripcion': descripciones[i],
                'precio': precio,
                'imagen_backblaze': url_backblaze,
                'imagen_github': url_github or '/static/img/fallback.webp',
                'grupo': grupo,
                'subgrupo': subgrupo,
                'orden': orden,
                'talles': talle_lista
            })

        session['bloques'] = bloques
        exitos = 0

        def subir_con_resultado(producto):
            try:
                return subir_a_firestore(producto, email)
            except Exception:
                return False

        bloques_por_lote = 10
        for inicio in range(0, len(bloques), bloques_por_lote):
            lote = bloques[inicio:inicio + bloques_por_lote]
            with ThreadPoolExecutor(max_workers=3) as executor:
                resultados = list(executor.map(subir_con_resultado, lote))
            exitos += sum(1 for r in resultados if r)

        if github_token and repo_name:
            try:
                html = render_template(
                    'preview.html',
                    config=session,
                    grupos={},
                    modoAdmin=False,
                    modoAdminIntentado=False,
                    firebase_config=firebase_config
                )
                subir_archivo(repo_name, html.encode('utf-8'), 'index.html', github_token)
            except Exception:
                pass

            try:
                subir_iconos_png(repo_name, github_token)
            except Exception:
                pass

            logo = session.get('logo')
            if logo:
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        contenido = f.read()
                    subir_archivo(repo_name, contenido, f"static/img/{logo}", github_token)

            estilo_visual = session.get('estilo_visual') or 'claro_moderno'
            fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{estilo_visual}.jpeg")
            if os.path.exists(fondo_path):
                with open(fondo_path, "rb") as f:
                    contenido = f.read()
                subir_archivo(repo_name, contenido, f"static/img/{estilo_visual}.jpeg", github_token)

        if exitos > 0:
            return redirect('/preview')
        else:
            return render_template('step3.html', tipo_web=tipo, imagenes_step0=imagenes_disponibles)

    return render_template('step3.html', tipo_web=tipo, imagenes_step0=imagenes_disponibles)
    
def get_mp_public_key(email: str):
    """
    Obtiene la public_key de Mercado Pago para el vendedor.
    - 1) Intenta leerla de Firestore.
    - 2) Si está en null o vacía, intenta recuperarla en vivo usando el access_token del vendedor:
         a) /v1/account/credentials
         b) Fallback: /users/me
    - 3) Si la obtiene, la guarda en Firestore y la retorna.
    - 4) Si todo falla, usa env MP_PUBLIC_KEY (fallback global).
    """
    # 1) Leer desde Firestore
    try:
        if email:
            doc_ref = db.collection("usuarios").document(email).collection("config").document("mercado_pago")
            snap = doc_ref.get()
            if snap.exists:
                data = snap.to_dict()
                pk = data.get("public_key")
                if pk and isinstance(pk, str) and pk.strip():
                    print(f"[MP-HELPER] Firestore public_key OK para {email}")
                    return pk.strip()
                else:
                    print(f"[MP-HELPER] Firestore public_key vacío para {email}, intentando recuperar en vivo...")
    except Exception as e:
        print(f"[MP-HELPER] Error leyendo Firestore: {e}")

    # 2) Recuperar en vivo con access_token del vendedor
    access_token = None
    try:
        access_token = get_mp_token(email)
    except Exception as e:
        print(f"[MP-HELPER] Error obteniendo access_token: {e}")

    public_key = None
    if access_token and isinstance(access_token, str):
        # a) Intento con /v1/account/credentials
        try:
            resp = requests.get(
                "https://api.mercadopago.com/v1/account/credentials",
                headers={"Authorization": f"Bearer {access_token.strip()}"},
                timeout=10
            )
            print(f"[MP-HELPER] credentials status={resp.status_code}")
            if resp.status_code == 200:
                data = resp.json() or {}
                public_key = (data.get("public_key") or data.get("web", {}).get("public_key") or "").strip()
        except Exception as e:
            print(f"[MP-HELPER] Error en credentials: {e}")

        # b) Fallback /users/me
        if not public_key:
            try:
                resp = requests.get(
                    "https://api.mercadopago.com/users/me",
                    headers={"Authorization": f"Bearer {access_token.strip()}"},
                    timeout=10
                )
                print(f"[MP-HELPER] users/me status={resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json() or {}
                    public_key = (data.get("public_key") or "").strip()
            except Exception as e:
                print(f"[MP-HELPER] Error en users/me: {e}")

        # 3) Guardar si existe
        if public_key:
            try:
                db.collection("usuarios").document(email).collection("config").document("mercado_pago").set({
                    "public_key": public_key,
                    "updated_at": datetime.now().isoformat()
                }, merge=True)
                print(f"[MP-HELPER] ✅ public_key recuperada y guardada para {email}")
                return public_key
            except Exception as e:
                print(f"[MP-HELPER] Error guardando public_key en Firestore: {e}")
        else:
            print("[MP-HELPER] ❌ No se pudo recuperar public_key en vivo")
    else:
        print("[MP-HELPER] ❌ No hay access_token del vendedor para recuperar public_key")

    # 4) Fallback de entorno
    pk_env = os.getenv("MP_PUBLIC_KEY")
    if pk_env and isinstance(pk_env, str) and pk_env.strip():
        print(f"[MP-HELPER] Usando MP_PUBLIC_KEY del entorno")
        return pk_env.strip()

    return None

@app.route('/conectar_mp')
def conectar_mp():
    if not session.get('modo_admin'):
        return redirect(url_for('preview'))

    client_id = os.getenv("MP_CLIENT_ID")
    redirect_uri = url_for('callback_mp', _external=True)

    if not client_id:
        flash("❌ Falta configurar MP_CLIENT_ID en entorno")
        return redirect(url_for('preview', admin='true'))

    # URL oficial de autorización con todos los scopes necesarios
    auth_url = (
        "https://auth.mercadopago.com/authorization?"
        f"client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read%20write%20offline_access"
    )
    print(f"[MP-CONNECT] Redirigiendo a: {auth_url}")
    return redirect(auth_url)


@app.route('/callback_mp')
def callback_mp():
    if not session.get('modo_admin'):
        return redirect(url_for('preview'))

    code = request.args.get('code')
    client_id = os.getenv("MP_CLIENT_ID")
    client_secret = os.getenv("MP_CLIENT_SECRET")
    redirect_uri = url_for('callback_mp', _external=True)

    if not code:
        flash("❌ No se recibió código de autorización")
        return redirect(url_for('preview', admin='true'))

    token_url = "https://api.mercadopago.com/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }

    try:
        print(f"[MP-CALLBACK] Enviando payload a {token_url}: {payload}")
        response = requests.post(token_url, data=payload, timeout=10)
        print(f"[MP-CALLBACK] Status token_url={response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"[MP-CALLBACK] Respuesta token: {data}")

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token:
            print("[MP-CALLBACK] ❌ No se recibió access_token")
            flash("❌ Error al obtener token de Mercado Pago")
            return redirect(url_for('preview', admin='true'))

        # ✅ Obtener la public_key
        public_key = data.get("public_key")
        if public_key and isinstance(public_key, str):
            public_key = public_key.strip()
        else:
            try:
                print("[MP-CALLBACK] Intentando obtener public_key desde /v1/account/credentials")
                cred_resp = requests.get(
                    "https://api.mercadopago.com/v1/account/credentials",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10
                )
                print(f"[MP-CALLBACK] Status credentials={cred_resp.status_code}")
                if cred_resp.status_code == 200:
                    cred_data = cred_resp.json() or {}
                    print(f"[MP-CALLBACK] Datos credentials: {cred_data}")
                    public_key = cred_data.get("public_key") or cred_data.get("web", {}).get("public_key")

                if not public_key:
                    print("[MP-CALLBACK] Intentando obtener public_key desde /users/me")
                    user_resp = requests.get(
                        "https://api.mercadopago.com/users/me",
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=10
                    )
                    print(f"[MP-CALLBACK] Status users/me={user_resp.status_code}")
                    if user_resp.status_code == 200:
                        user_data = user_resp.json() or {}
                        print(f"[MP-CALLBACK] Datos users/me: {user_data}")
                        public_key = user_data.get("public_key")

                if public_key and isinstance(public_key, str):
                    public_key = public_key.strip()
            except Exception as e:
                print("Error al obtener public_key:", e)
                public_key = None

        # ✅ Guardar credenciales en Firestore sin pisar public_key con null
        email = session.get('email')
        if email:
            doc_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "created_at": datetime.now().isoformat(),
                # datos útiles para auditoría
                "live_mode": data.get("live_mode"),
                "scope": data.get("scope"),
                "user_id": data.get("user_id"),
            }
            if public_key:  # solo si existe
                doc_data["public_key"] = public_key

            db.collection("usuarios").document(email).collection("config").document("mercado_pago").set(
                doc_data, merge=True
            )
            print(
                f"[MP-CALLBACK] Guardado: "
                f"access_token={'SET' if access_token else 'MISSING'} "
                f"refresh_token={'SET' if refresh_token else 'MISSING'} "
                f"public_key={'SET' if public_key else 'UNCHANGED'}"
            )
        else:
            print("[MP-CALLBACK] ⚠️ No hay email en sesión, no se guardó en Firestore")

        flash("✅ Mercado Pago conectado correctamente")
        return redirect(url_for('preview', admin='true'))

    except Exception as e:
        print("Error en callback_mp:", e)
        flash("Error al conectar con Mercado Pago")
        return redirect(url_for('preview', admin='true'))

@app.route('/pagar', methods=['POST'])
def pagar():
    try:
        data = request.get_json(silent=True) or {}
        carrito = data.get('carrito', [])

        email = session.get('email')
        if not email:
            return jsonify({'error': 'Sesión no iniciada'}), 403

        access_token = get_mp_token(email)
        if not access_token or not isinstance(access_token, str):
            return jsonify({'error': 'El vendedor no tiene credenciales de Mercado Pago configuradas'}), 400

        sdk = mercadopago.SDK(access_token.strip())

        # ✅ Validar carrito
        if not carrito or not isinstance(carrito, list):
            return jsonify({'error': 'Carrito vacío o inválido'}), 400

        items = []
        for item in carrito:
            try:
                items.append({
                    "id": item.get('sku') or f"SKU_{item.get('id', '0')}",
                    "title": item.get('nombre', 'Producto') + (f" ({item.get('talle')})" if item.get('talle') else ""),
                    "description": item.get('descripcion') or item.get('nombre', 'Producto'),
                    "category_id": item.get('category_id') or "others",
                    "quantity": int(item.get('cantidad', 1)),
                    "unit_price": float(item.get('precio', 0)),
                    "currency_id": "ARS"
                })
            except Exception as e:
                print(f"[PAGAR] Error procesando item: {e}")

        print(f"[PAGAR] Items generados: {items}")

        external_ref = "pedido_" + datetime.now().strftime("%Y%m%d%H%M%S")

        preference_data = {
            "items": items,
            "back_urls": {
                "success": url_for('pago_success', _external=True),
                "failure": url_for('pago_failure', _external=True),
                "pending": url_for('pago_pending', _external=True)
            },
            "auto_return": "approved",
            "statement_descriptor": "TuEmprendimiento",
            "external_reference": external_ref,
            "notification_url": url_for('webhook_mp', _external=True)
        }

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {}) or {}
        print(f"[PAGAR] Respuesta preferencia: {preference}")

        if not preference.get("id"):
            return jsonify({'error': 'No se pudo generar la preferencia de pago'}), 500

        return jsonify({
            "preference_id": preference["id"],
            "init_point": preference.get("init_point"),
            "external_reference": external_ref
        })

    except Exception as e:
        print(f"[PAGAR] Error interno: {e}")
        return jsonify({'error': 'Error interno al generar el pago', 'message': str(e)}), 500

@app.route('/preview')
def preview():
    modo_admin = bool(session.get('modo_admin')) and request.args.get('admin') == 'true'
    modo_admin_intentado = request.args.get('admin') == 'true'
    email = session.get('email')

    if not email:
        print("[Preview] ❌ Sesión no iniciada")
        return "Error: sesión no iniciada", 403

    estilo_visual = session.get('estilo_visual') or 'claro_moderno'
    print(f"[Preview] email={email} estilo_visual={estilo_visual}")

    # Obtener productos desde Firestore
    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        productos_docs = productos_ref.stream()
        productos = [doc.to_dict() for doc in productos_docs]
        print(f"[Preview] Productos obtenidos: {len(productos)}")
    except Exception as e:
        print("[Preview] Error al leer productos:", e)
        productos = []

    # Agrupar por grupo y subgrupo
    grupos_dict = {}
    for producto in productos:
        grupo = (producto.get('grupo') or 'General').strip().title()
        subgrupo = (producto.get('subgrupo') or 'Sin subgrupo').strip().title()
        grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)
    print(f"[Preview] Grupos generados: {list(grupos_dict.keys())}")

    # Credenciales de Mercado Pago
    mercado_pago_token = get_mp_token(email)
    public_key = get_mp_public_key(email) or ""  # nunca None

    print(f"[Preview] email={email} mercado_pago_token={bool(mercado_pago_token)} public_key={public_key}")

    # Configuración visual
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
        'mercado_pago': bool(mercado_pago_token),
        'public_key': public_key,
        'productos': productos,
        'bloques': [],
        'descargado': session.get('descargado', False),
        'usarFirestore': True
    }

    # Crear repo si corresponde
    if session.get("crear_repo") and not session.get("repo_creado"):
        nombre_repo = generar_nombre_repo(email)
        token = os.getenv("GITHUB_TOKEN")
        resultado = crear_repo_github(nombre_repo, token)
        print(f"[Preview] Creando repo: {nombre_repo}, resultado={resultado}")
        if "url" in resultado:
            session['repo_creado'] = resultado["url"]
            session['repo_nombre'] = nombre_repo

    # Subir archivos si el repo existe
    if session.get('repo_creado') and session.get('repo_nombre'):
        nombre_repo = session['repo_nombre']
        token = os.getenv("GITHUB_TOKEN")
        print(f"[Preview] Subiendo archivos al repo: {nombre_repo}")

        if token:
            try:
                for producto in productos:
                    imagen = producto.get("imagen_github") or producto.get("imagen_backblaze")
                    if imagen and imagen.startswith("/static/img/"):
                        ruta_local = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(imagen))
                        if os.path.exists(ruta_local):
                            with open(ruta_local, "rb") as f:
                                contenido = f.read()
                            subir_archivo(nombre_repo, contenido, f"static/img/{os.path.basename(imagen)}", token)
                            print(f"[Preview] Imagen subida: {imagen}")
                            del contenido
                            gc.collect()

                logo = config.get("logo")
                if logo:
                    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                    if os.path.exists(logo_path):
                        with open(logo_path, "rb") as f:
                            contenido = f.read()
                        subir_archivo(nombre_repo, contenido, f"static/img/{logo}", token)
                        print(f"[Preview] Logo subido: {logo}")
                        del contenido
                        gc.collect()

                fondo = f"{estilo_visual}.jpeg"
                fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
                if os.path.exists(fondo_path):
                    with open(fondo_path, "rb") as f:
                        contenido = f.read()
                    subir_archivo(nombre_repo, contenido, f"static/img/{fondo}", token)
                    print(f"[Preview] Fondo subido: {fondo}")
                    del contenido
                    gc.collect()
            except Exception as e:
                print("[Preview] Error al subir archivos al repo:", e)

    try:
        print("[Preview] Renderizando template preview.html")
        return render_template(
            'preview.html',
            config=config,
            grupos=grupos_dict,
            modoAdmin=modo_admin,
            modoAdminIntentado=modo_admin_intentado,
            firebase_config=firebase_config   # 👈 aquí usás la global definida arriba
        )
    except Exception as e:
        print("[Preview] Error al renderizar preview:", e)
        return "Internal Server Error al renderizar preview", 500

@app.route('/descargar')
def descargar():
    email = session.get('email')
    if not email:
        return "Error: sesión no iniciada", 403

    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        productos_docs = productos_ref.stream()
        productos = [doc.to_dict() for doc in productos_docs]
    except Exception:
        productos = []

    grupos = {}
    for producto in productos:
        grupo = producto.get('grupo', 'General').strip().title()
        subgrupo = producto.get('subgrupo', 'Sin subgrupo').strip().title()
        grupos.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)

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
        'productos': productos,
        'bloques': []
    }

    html = render_template('preview.html', config=config, grupos=grupos)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('index.html', html)

        fondo = f"{estilo_visual}.jpeg"
        fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
        if os.path.exists(fondo_path):
            zip_file.write(fondo_path, arcname='img/' + fondo)

        for producto in productos:
            imagen = producto.get('imagen')
            if imagen:
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen)
                if os.path.exists(imagen_path):
                    zip_file.write(imagen_path, arcname='img/' + imagen)

        logo = config.get("logo")
        if logo:
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
            if os.path.exists(logo_path):
                zip_file.write(logo_path, arcname='img/' + logo)

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
