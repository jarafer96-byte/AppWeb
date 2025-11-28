from flask import Flask, render_template, redirect, session, send_file, url_for, jsonify, current_app, request, flash
import requests
import os
import uuid
import re
import time
import json
import gc
import pandas as pd
import traceback
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from io import BytesIO
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import shortuuid
import mercadopago
import base64
import firebase_admin
from firebase_admin import credentials, firestore
from flask_cors import CORS, cross_origin
from google.cloud import storage
from google.oauth2 import service_account
import secrets

# 🔐 Inicialización segura de Firebase con logs
db = None
try:
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    print(f"[Firebase] Variable FIREBASE_CREDENTIALS_JSON encontrada: {bool(cred_json)}")

    if cred_json:
        cred_dict = json.loads(cred_json)
        print(f"[Firebase] Claves disponibles en cred_dict: {list(cred_dict.keys())}")

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print(f"✅ Firebase inicializado correctamente con app: {firebase_admin.get_app().name}")
    else:
        print("⚠️ FIREBASE_CREDENTIALS_JSON no configurado en entorno")

except Exception as e:
    print("❌ Error al inicializar Firebase:", e)
    import traceback
    print(traceback.format_exc())
    db = None

# Verificación final del cliente Firestore
if db:
    try:
        test_doc = db.collection("_debug").document("conexion").get()
        print(f"[Firebase] Conexión Firestore OK, doc.exists={test_doc.exists}")
    except Exception as e:
        print("💥 Error verificando conexión Firestore:", e)
else:
    print("⚠️ Firestore client no disponible (db=None)")


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
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024 
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "clave-secreta-temporal"
app.config['SESSION_COOKIE_SECURE'] = not app.debug

# Mantener las sesiones persistentes por defecto y duración
app.config['SESSION_PERMANENT'] = True
app.permanent_session_lifetime = timedelta(days=7)

firebase_config = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
}

# 🔑 Inicialización de Google Cloud Storage
key_json = os.environ.get("GOOGLE_CLOUD_KEY")
if not key_json:
    raise RuntimeError("Falta la variable GOOGLE_CLOUD_KEY en Render")

# Convertir el JSON pegado en dict
creds_dict = json.loads(key_json)

# Crear credenciales desde el dict
credentials = service_account.Credentials.from_service_account_info(creds_dict)

# Inicializar cliente con tu Project ID
client = storage.Client(credentials=credentials, project="arcane-sentinel-479319-g0")

# Bucket donde se guardan las imágenes
bucket = client.bucket("mpagina")

UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def subir_a_firestore(producto, email):
    try:
        print(f"[FIRESTORE] 🚀 Iniciando subida de producto para email={email}")
        print(f"[FIRESTORE] Datos recibidos: {producto}")

        if not isinstance(producto, dict):
            print("[FIRESTORE] ❌ Producto inválido (no es dict)")
            return {"ok": False, "error": "Producto inválido (no es dict)"}

        if not producto.get("nombre") or not producto.get("grupo") or not producto.get("precio"):
            print("[FIRESTORE] ❌ Faltan campos obligatorios: nombre/grupo/precio")
            return {"ok": False, "error": "Faltan campos obligatorios: nombre/grupo/precio"}

        grupo_original = producto["grupo"].strip()
        subgrupo_original = (producto.get("subgrupo", "") or "").strip() or f"General_{grupo_original}"
        nombre_original = producto["nombre"].strip()
        print(f"[FIRESTORE] Campos normalizados: nombre={nombre_original}, grupo={grupo_original}, subgrupo={subgrupo_original}")

        grupo_id = grupo_original.replace(" ", "_").lower()
        nombre_id = nombre_original.replace(" ", "_").lower()
        fecha = time.strftime("%Y%m%d")
        sufijo = uuid.uuid4().hex[:6]
        custom_id = f"{nombre_id}_{fecha}_{grupo_id}_{sufijo}"
        print(f"[FIRESTORE] ID generado: {custom_id}")

        # Parseo de precio
        precio_raw = producto["precio"]
        price_str = str(precio_raw).strip()
        price_clean = re.sub(r"[^\d,\.]", "", price_str)
        print(f"[FIRESTORE] Precio raw='{precio_raw}' | limpio='{price_clean}'")

        if "," in price_clean and "." in price_clean:
            price_clean = price_clean.replace(".", "").replace(",", ".")
        elif "," in price_clean and "." not in price_clean:
            price_clean = price_clean.replace(",", ".")
        try:
            precio_float = float(price_clean)
            precio = int(round(precio_float))
            print(f"[FIRESTORE] Precio final parseado: {precio}")
        except Exception as e:
            print(f"[FIRESTORE] ❌ Error parseando precio: {e}")
            return {"ok": False, "error": f"Formato de precio inválido: '{price_str}' -> '{price_clean}'", "detail": str(e)}

        try:
            orden = int(producto.get("orden", 999))
        except Exception:
            orden = 999
        print(f"[FIRESTORE] Orden final: {orden}")

        talles = producto.get("talles") or []
        if isinstance(talles, str):
            talles = [t.strip() for t in talles.split(',') if t.strip()]
        print(f"[FIRESTORE] Talles procesados: {talles}")

        producto["id_base"] = custom_id

        # Imagen: usar la URL real si ya viene del upload, si no, fallback a custom_id.webp
        imagen_url = producto.get("imagen_url")
        if imagen_url:
            print(f"[FIRESTORE] Usando imagen_url provista: {imagen_url}")
        else:
            imagen_nombre = f"{custom_id}.webp"
            # Importante: encode del email en la URL pública (%40 para '@')
            email_encoded = email.replace("@", "%40")
            imagen_url = f"https://storage.googleapis.com/mpagina/{email_encoded}/{imagen_nombre}"
            print(f"[FIRESTORE] Generada imagen_url por fallback: {imagen_url}")

        doc = {
            "nombre": nombre_original,
            "id_base": custom_id,
            "precio": precio,
            "grupo": grupo_original,
            "subgrupo": subgrupo_original,
            "descripcion": producto.get("descripcion", ""),
            "imagen_url": imagen_url,
            "orden": orden,
            "talles": talles,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        print(f"[FIRESTORE] Documento a guardar: {doc}")

        ruta = f"usuarios/{email}/productos/{custom_id}"
        print(f"[FIRESTORE] Guardando en ruta: {ruta}")
        db.collection("usuarios").document(email).collection("productos").document(custom_id).set(doc)
        print(f"[FIRESTORE] ✅ Producto guardado correctamente en Firestore: {custom_id} para {email}")

        return {"ok": True, "id": custom_id}

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[FIRESTORE] ❌ Error general al subir producto para {email}: {e}\n{tb}")
        return {"ok": False, "error": str(e), "trace": tb}

def subir_archivo(repo, contenido_bytes, ruta_remota, branch="main"):
    """
    Subida de archivo a GitHub con logs detallados.
    Retorna dict con estado y URLs.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("[GITHUB] ❌ Token de GitHub no disponible")
        return {"ok": False, "error": "Token de GitHub no disponible"}

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo}/contents/{ruta_remota}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }

    print(f"[GITHUB] 🚀 Iniciando subida de archivo")
    print(f"[GITHUB] Repo={repo}, Ruta remota={ruta_remota}, Branch={branch}")
    print(f"[GITHUB] URL destino: {url}")

    # Obtener SHA si el archivo ya existe
    sha = None
    try:
        r_get = requests.get(url, headers=headers, timeout=10)
        print(f"[GITHUB] GET status={r_get.status_code}")
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")
            print(f"[GITHUB] Archivo existente, SHA={sha}")
        else:
            print(f"[GITHUB] Archivo no existe aún en repo (status={r_get.status_code})")
    except Exception as e:
        print(f"[GITHUB] ⚠️ Error obteniendo SHA: {e}")
        sha = None

    data = {
        "message": f"Actualización automática de {ruta_remota}",
        "content": base64.b64encode(contenido_bytes).decode("utf-8"),
        "branch": branch
    }
    if sha:
        data["sha"] = sha
        print(f"[GITHUB] Incluyendo SHA en payload para actualizar archivo")

    try:
        r = requests.put(url, headers=headers, json=data, timeout=10)
        print(f"[GITHUB] PUT status={r.status_code}")
        if r.status_code in (200, 201):
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{repo}/{branch}/{ruta_remota}"
            html_url = r.json().get("content", {}).get("html_url")
            print(f"[GITHUB] ✅ Subida exitosa: html_url={html_url}, raw_url={raw_url}")
            return {
                "ok": True,
                "url": html_url,
                "raw_url": raw_url,
                "status": r.status_code
            }
        else:
            print(f"[GITHUB] ❌ Error en subida: status={r.status_code}, error={r.text}")
            return {"ok": False, "status": r.status_code, "error": r.text}
    except Exception as e:
        print(f"[GITHUB] 💥 Excepción en PUT: {e}")
        import traceback
        print(traceback.format_exc())
        return {"ok": False, "error": str(e)}

@app.route("/subir-foto", methods=["POST"])
def subir_foto():
    try:
        # 1) Obtener archivo y email
        file = request.files.get("file")
        email = request.form.get("email")

        if not file or not email:
            return jsonify({"error": "Falta archivo o email"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Formato inválido. Usa png/jpg/jpeg/webp"}), 400

        # 2) Validar tamaño por si llega sin respetar MAX_CONTENT_LENGTH
        file.seek(0, 2)  # ir al final
        size = file.tell()
        file.seek(0)     # volver al inicio
        if size > MAX_IMAGE_SIZE_BYTES:
            return jsonify({"error": "Imagen excede 3 MB"}), 413

        # 3) Nombre seguro y único
        original_name = secure_filename(file.filename)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{original_name}"

        # 4) Ruta organizada por email
        # Tip: si querés evitar caracteres raros en email como ".", "@", podés reemplazarlos
        email_path = email.replace("@", "_at_").replace(".", "_dot_")
        blob_path = f"usuarios/{email_path}/imagenes/{filename}"

        # 5) Subir al bucket con content_type correcto
        blob = bucket.blob(blob_path)
        blob.upload_from_file(file, content_type=file.content_type or "image/jpeg")

        # 6) Hacer público y devolver URL
        blob.make_public()
        public_url = blob.public_url

        print(f"[Upload] {email} -> {blob_path} ({size} bytes)")
        return jsonify({"url": public_url, "path": blob_path})

    except Exception as e:
        print("[Upload][Error]", str(e))
        return jsonify({"error": str(e)}), 500
        
@app.route("/api/productos")
def api_productos():
    # Permitir email desde sesión (preview/admin) o desde query string (index público)
    email = session.get("email") or request.args.get("usuario")
    if not email:
        return jsonify({"error": "No se especificó usuario"}), 403

    try:
        # Colección de productos del usuario
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        docs = productos_ref.stream()

        productos = []
        for doc in docs:
            data = doc.to_dict() or {}
            productos.append({
                "id": doc.id,
                "id_base": data.get("id_base"),
                "nombre": data.get("nombre"),
                "precio": data.get("precio"),
                "grupo": data.get("grupo"),
                "subgrupo": data.get("subgrupo"),
                "descripcion": data.get("descripcion"),
                "imagen_url": data.get("imagen_url"),
                "orden": data.get("orden"),
                "talles": data.get("talles", []),
                "timestamp": str(data.get("timestamp")) if data.get("timestamp") else None
            })

        # Ordenar por 'orden'
        productos = sorted(productos, key=lambda p: p.get("orden") or 0)

        return jsonify(productos)

    except Exception as e:
        print(f"[API_PRODUCTOS] Error al leer productos: {e}")
        return jsonify({"error": str(e)}), 500
        
@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        email = session.get("email", "anonimo")
        imagenes = request.files.getlist('imagenes')

        print("📥 [UPLOAD] Iniciando subida de imágenes de usuario...")
        print(f"👤 [UPLOAD] Usuario: {email}")
        print(f"📦 [UPLOAD] Cantidad recibida: {len(imagenes)}")

        if not imagenes:
            print("⚠️ [UPLOAD] No se recibieron imágenes en la request")
            return jsonify({"ok": False, "error": "No se recibieron imágenes"}), 400

        if 'imagenes_step0' not in session:
            session['imagenes_step0'] = []

        urls = []
        for idx, img in enumerate(imagenes, start=1):
            if img and img.filename:
                try:
                    contenido_bytes = img.read()
                    ext = os.path.splitext(img.filename)[1].lower() or ".webp"
                    filename = f"{uuid.uuid4().hex}{ext}"

                    print(f"➡️ [UPLOAD] Procesando {idx}/{len(imagenes)}: {img.filename}")
                    print(f"📝 [UPLOAD] Nombre generado: {filename}, Extensión: {ext}")
                    print(f"📏 [UPLOAD] Tamaño en bytes: {len(contenido_bytes)}")

                    # 🔎 Log de credenciales y bucket
                    print(f"🔑 [UPLOAD] Bucket activo: {bucket.name}")
                    print(f"🔑 [UPLOAD] Email service account: {credentials.service_account_email}")

                    # Subir a Google Cloud Storage
                    blob_path = f"{email}/{filename}"
                    print(f"🚀 [UPLOAD] Intentando subir a GCS en ruta: {blob_path}")
                    blob = bucket.blob(blob_path)

                    blob.upload_from_string(contenido_bytes, content_type="image/webp")
                    print(f"📤 [UPLOAD] Upload_from_string completado")

                    # ✅ Construir URL pública sin usar ACL (UBLA activo)
                    ruta_publica = f"https://storage.googleapis.com/{bucket.name}/{blob_path}"
                    print(f"🌍 [UPLOAD] URL pública generada: {ruta_publica}")

                    urls.append(ruta_publica)
                    session['imagenes_step0'].append(ruta_publica)
                    print(f"✅ [UPLOAD] Subida exitosa a GCS: {ruta_publica}")

                except Exception as e:
                    print(f"💥 [UPLOAD] Error procesando {img.filename}: {e}", flush=True)
                    import traceback; traceback.print_exc()
                    return jsonify({"ok": False, "error": str(e)}), 500

        print(f"📊 [UPLOAD] Total subidas correctas: {len(urls)}")
        print(f"📊 [UPLOAD] Total en sesión: {len(session['imagenes_step0'])}")

        return jsonify({"ok": True, "imagenes": urls})

    except Exception as e:
        print(f"💥 [UPLOAD] Error general en /upload-image: {e}", flush=True)
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

def subir_iconos_png(repo):
    carpeta = os.path.join("static", "img")
    for nombre_archivo in os.listdir(carpeta):
        if nombre_archivo.lower().endswith(".png"):
            ruta_local = os.path.join(carpeta, nombre_archivo)
            ruta_remota = f"static/img/{nombre_archivo}"
            with open(ruta_local, "rb") as f:
                contenido = f.read()
            subir_archivo(repo, contenido, ruta_remota)

def generar_nombre_repo(email):
    base = email.replace("@", "_at_").replace(".", "_")
    fecha = time.strftime("%Y%m%d")
    return f"{base}_{fecha}"

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

@app.route('/step0', methods=['GET'])
def step0():
    """
    Step0 ahora solo muestra el formulario para seleccionar y optimizar imágenes.
    La subida se hace exclusivamente vía /upload-image desde el frontend.
    """
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

            # 🔑 generar token único y guardarlo en sesión
            token = secrets.token_urlsafe(32)
            session['token_admin'] = token

            return jsonify({'status': 'ok', 'token': token})
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
    data = request.get_json(silent=True) or {}
    usuario = data.get("email")   # 👈 ahora viene del body
    producto = data.get("producto")

    if not usuario:
        return jsonify({'status': 'error', 'message': 'Falta email'}), 403

    if not producto:
        return jsonify({'status': 'error', 'message': 'Producto inválido'}), 400

    try:
        ruta = f"usuarios/{usuario}/productos"
        db.collection(ruta).add(producto)
        print(f"✅ Producto guardado para {usuario}: {producto.get('nombre', 'sin nombre')}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("❌ Error al guardar producto:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Agregar en app.py (temporal, para debug) ---
@app.route('/debug/session')
def debug_session():
    try:
        sess = dict(session)
    except Exception:
        sess = str(session)
    info = {
        "session_keys": list(session.keys()),
        "session": sess,
        "imagenes_step0": session.get("imagenes_step0"),
        "email": session.get("email"),
        "repo_nombre": session.get("repo_nombre"),
    }
    # intentar leer un doc pequeño (solo para verificar conexión Firestore, sin escribir)
    try:
        test_email = session.get("email") or "_debug_"
        doc = db.collection("usuarios").document(test_email).get()
        info["firestore_doc_exist_for_session_email"] = doc.exists
    except Exception as e:
        info["firestore_error"] = str(e)
    return jsonify(info)
# --- Fin debug ---

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
    email = data.get("email") 

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
    data = request.get_json() or {}
    id_base = data.get("id")
    nuevos_talles = data.get("talles", [])
    email = data.get("email")   # 👈 ahora viene del body

    if not email or not id_base:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            return jsonify({"error": "Producto no encontrado"}), 404

        doc = query[0]
        doc.reference.update({"talles": nuevos_talles})
        print(f"[ACTUALIZAR-TALLES] ✅ Usuario={email}, id_base={id_base}, talles={nuevos_talles}")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[ACTUALIZAR-TALLES] ❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/actualizar-firestore', methods=['POST'])
def actualizar_firestore():
    data = request.get_json(silent=True) or {}
    id_base = data.get("id")          # 👈 explícito
    email = data.get("email")         # 👈 explícito
    campos = {k: v for k, v in data.items() if k not in ("id", "email")}

    if not email or not id_base or not campos:
        return jsonify({'status': 'error', 'message': 'Datos incompletos'}), 400

    try:
        print(f"[ACTUALIZAR] Usuario={email}, id_base={id_base}, campos={campos}")
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            return jsonify({'status': 'error', 'message': 'Producto no encontrado'}), 404

        doc = query[0]
        doc.reference.update(campos)
        print(f"[ACTUALIZAR] ✅ Firestore actualizado para {id_base}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[ACTUALIZAR] ❌ Error: {e}")
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
    print("🚀 [Step3] Entrando a /contenido")
    tipo = session.get('tipo_web')
    email = session.get('email')
    imagenes_disponibles = session.get('imagenes_step0') or []
    print(f"🔑 [Step3] tipo_web={tipo}, email={email}, imagenes_disponibles={len(imagenes_disponibles)}")

    if not email:
        print("❌ [Step3] Sesión no iniciada")
        return "Error: sesión no iniciada", 403

    if request.method == 'POST':
        print("📥 [Step3] POST recibido")
        bloques = []
        nombres = request.form.getlist('nombre')
        descripciones = request.form.getlist('descripcion')
        precios = request.form.getlist('precio')
        grupos = request.form.getlist('grupo')
        subgrupos = request.form.getlist('subgrupo')
        ordenes = request.form.getlist('orden')
        talles = request.form.getlist('talles')
        imagenes_elegidas = request.form.getlist('imagen_elegida')

        print(f"📊 [Step3] Datos recibidos: nombres={len(nombres)}, precios={len(precios)}, imagenes_elegidas={len(imagenes_elegidas)}")

        repo_name = session.get('repo_nombre') or "AppWeb"
        print(f"📦 [Step3] Repo destino: {repo_name}")

        for i in range(len(nombres)):
            nombre = nombres[i].strip()
            precio = precios[i].strip()
            grupo = grupos[i].strip() or 'Sin grupo'
            subgrupo = subgrupos[i].strip() or 'Sin subgrupo'
            orden = ordenes[i].strip() or str(i + 1)

            print(f"➡️ [Step3] Procesando producto {i+1}: nombre={nombre}, precio={precio}, grupo={grupo}, subgrupo={subgrupo}, orden={orden}")

            if not nombre or not precio or not grupo or not subgrupo:
                print("⚠️ [Step3] Producto ignorado por datos incompletos")
                continue

            talle_raw = talles[i].strip() if i < len(talles) else ''
            talle_lista = [t.strip() for t in talle_raw.split(',') if t.strip()]
            print(f"👕 [Step3] Talles={talle_lista}")

            imagen_url = imagenes_elegidas[i].strip() if i < len(imagenes_elegidas) else ''
            imagen_para_guardar = None

            if not imagen_url:
                print(f"⚠️ [Step3] Imagen vacía para producto {nombre}")
                continue

            if imagen_url.startswith('/static/img/') or imagen_url.startswith('static/img/'):
                imagen_para_guardar = imagen_url if imagen_url.startswith('/') else '/' + imagen_url
            elif imagen_url.startswith('http://') or imagen_url.startswith('https://'):
                imagen_para_guardar = imagen_url
            else:
                basename = os.path.basename(imagen_url)
                session_imgs = session.get('imagenes_step0') or []
                matched = next((u for u in session_imgs if u.endswith(basename)), None)
                if matched:
                    imagen_para_guardar = matched
                else:
                    local_candidate = os.path.join(app.config['UPLOAD_FOLDER'], basename)
                    if os.path.exists(local_candidate):
                        imagen_para_guardar = f"/static/img/{basename}"
                    else:
                        print(f"⚠️ [Step3] Imagen inválida/no encontrada para producto {nombre}: {imagen_url} (basename: {basename})")
                        continue

            print(f"🔍 [Step3] imagen_para_guardar para '{nombre}': {imagen_para_guardar}")

            bloques.append({
                'nombre': nombre,
                'descripcion': descripciones[i],
                'precio': precio,
                'imagen_url': imagen_para_guardar,
                'grupo': grupo,
                'subgrupo': subgrupo,
                'orden': orden,
                'talles': talle_lista
            })
            print(f"✅ [Step3] Producto agregado: {nombre} con imagen {imagen_para_guardar}")

        session['bloques'] = bloques
        print(f"📊 [Step3] Total bloques construidos: {len(bloques)}")
        exitos = 0

        def subir_con_resultado(producto):
            try:
                resultado = subir_a_firestore(producto, email)
                print(f"🔥 [Step3] Resultado subir_a_firestore para '{producto.get('nombre')}' -> {resultado}")
                return resultado.get("ok") if isinstance(resultado, dict) else bool(resultado)
            except Exception as e:
                print(f"💥 [Step3] Excepción en subir_con_resultado: {e}")
                print(traceback.format_exc())
                return False

        bloques_por_lote = 10
        for inicio in range(0, len(bloques), bloques_por_lote):
            lote = bloques[inicio:inicio + bloques_por_lote]
            print(f"📦 [Step3] Subiendo lote {inicio//bloques_por_lote+1} con {len(lote)} productos")
            with ThreadPoolExecutor(max_workers=3) as executor:
                resultados = list(executor.map(subir_con_resultado, lote))
            exitos += sum(1 for r in resultados if r)
        print(f"📊 [Step3] Total exitos en Firestore: {exitos}")

        grupos_dict = {}
        for producto in bloques:
            grupo = (producto.get('grupo') or 'General').strip().title()
            subgrupo = (producto.get('subgrupo') or 'Sin subgrupo').strip().title()
            grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)
        print(f"📂 [Step3] Grupos generados: {list(grupos_dict.keys())}")

        if repo_name:
            try:
                print("⬆️ [Step3] Renderizando preview.html para subir a GitHub")
                html = render_template(
                    'preview.html',
                    config=session,
                    grupos=grupos_dict,
                    modoAdmin=False,
                    modoAdminIntentado=False,
                    firebase_config=firebase_config
                )
                subir_archivo(repo_name, html.encode('utf-8'), 'index.html')
                print("✅ [Step3] index.html subido a GitHub")
            except Exception as e:
                print("[Step3] Error subiendo index.html:", e)

            try:
                subir_iconos_png(repo_name)
                print("✅ [Step3] Iconos subidos a GitHub")
            except Exception as e:
                print("[Step3] Error subiendo iconos:", e)

            logo = session.get('logo')
            if logo:
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                print(f"🔍 [Step3] Verificando logo: {logo_path}")
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        contenido = f.read()
                    subir_archivo(repo_name, contenido, f"static/img/{logo}")
                    print(f"✅ [Step3] Logo subido: {logo}")

            estilo_visual = session.get('estilo_visual')
            fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{estilo_visual}.jpeg")
            print(f"🔍 [Step3] Verificando fondo: {fondo_path}")
            if os.path.exists(fondo_path):
                with open(fondo_path, "rb") as f:
                    contenido = f.read()
                subir_archivo(repo_name, contenido, f"static/img/{estilo_visual}.jpeg")
                print(f"✅ [Step3] Fondo subido: {estilo_visual}.jpeg")

        if exitos > 0:
            print("➡️ [Step3] Redirigiendo a /preview")
            return redirect('/preview')
        else:
            print("⚠️ [Step3] Ningún producto subido, renderizando step3.html")
            return render_template(
                'step3.html',
                tipo_web=tipo,
                imagenes_step0=imagenes_disponibles,
                email=email   # 👈 agregado
            )

    print("ℹ️ [Step3] GET request, renderizando step3.html")
    return render_template(
        'step3.html',
        tipo_web=tipo,
        imagenes_step0=imagenes_disponibles,
        email=email   # 👈 agregado
    )

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
    if not db:
        return jsonify({'error': 'El servicio de base de datos no está disponible (Firestore)'}), 503
        
    try:
        # 1. Recibir y validar datos base
        data = request.get_json(silent=True) or {}
        carrito = data.get('carrito', [])
        email_vendedor = data.get('email_vendedor')  # <-- Viene del frontend

        if not email_vendedor:
            return jsonify({'error': 'Falta identificar al vendedor'}), 400

        # 2. Obtener Token de Mercado Pago
        access_token = get_mp_token(email_vendedor)
        if not access_token or not isinstance(access_token, str):
            return jsonify({'error': 'Vendedor sin credenciales MP o credenciales inválidas'}), 400

        sdk = mercadopago.SDK(access_token.strip())

        if not carrito or not isinstance(carrito, list):
            return jsonify({'error': 'Carrito vacío o inválido'}), 400

        items_mp = []
        productos_ref = db.collection("usuarios").document(email_vendedor).collection("productos")

        for item_frontend in carrito:
            # Necesitamos solo el ID y la cantidad/talle. El precio del frontend es ignorado.
            id_base = item_frontend.get('id_base') 
            
            # Sanitización y validación de cantidad
            try:
                cantidad = int(item_frontend.get('cantidad', 1))
                if cantidad <= 0:
                    raise ValueError("Cantidad inválida")
            except:
                cantidad = 1 # Fallback seguro
            
            talle = item_frontend.get('talle', '')
            
            if not id_base:
                print(f"⚠️ Item inválido o sin id_base. Saltando.")
                continue 

            # A) Buscamos el producto REAL en Firestore
            prod_doc = productos_ref.document(id_base).get()

            if prod_doc.exists:
                prod_real = prod_doc.to_dict()
                precio_real = float(prod_real.get('precio', 0))
                
                # Previene precios cero o negativos
                if precio_real <= 0:
                    print(f"⚠️ Producto {id_base} con precio no válido ({precio_real}). Saltando.")
                    continue

                nombre_real = prod_real.get('nombre', 'Producto Desconocido')
                
                # B) Construimos el ítem de MP usando SÓLO los datos de la BD
                items_mp.append({
                    "id": id_base,
                    "title": f"{nombre_real}{f' ({talle})' if talle else ''}", 
                    "description": nombre_real,
                    "quantity": cantidad,
                    "unit_price": precio_real, # <--- ✅ EL PRECIO PROVIENE DE FIRESTORE
                    "currency_id": "ARS"
                })
            else:
                print(f"⚠️ Producto con id_base {id_base} no encontrado en BD. Saltando.")

        if not items_mp:
            return jsonify({'error': 'No se pudieron validar productos en el carrito. Todos los ítems son inválidos.'}), 400

        # 4. Preparar Preferencia de Pago
        external_ref = "pedido_" + datetime.now().strftime("%Y%m%d%H%M%S")
        url_retorno = data.get('url_retorno', 'https://google.com').split("?")[0] 

        preference_data = {
            "items": items_mp,
            "back_urls": {
                "success": f"{url_retorno}?status=success",
                "failure": f"{url_retorno}?status=failure",
                "pending": f"{url_retorno}?status=pending"
            },
            "auto_return": "approved",
            "statement_descriptor": "TuEmprendimiento", 
            "external_reference": external_ref,
            "notification_url": url_for('webhook_mp', _external=True)
        }

        # 5. Crear Preferencia
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {}) or {}

        if not preference.get("id"):
            print(f"[PAGAR] Error al generar preferencia: {preference_response.get('message')}")
            return jsonify({'error': 'No se pudo generar la preferencia de pago en MP'}), 500

        # 6. Devolver resultado al frontend
        return jsonify({
            "preference_id": preference.get("id"),
            "init_point": preference.get("init_point"),
            "external_reference": external_ref
        })

    except Exception as e:
        print(f"[PAGAR] Error interno: {e}")
        traceback.print_exc() 
        return jsonify({'error': 'Error interno al generar el pago', 'message': str(e)}), 500
        
@app.route('/preview', methods=["GET", "POST"])
def preview():
    print("🚀 [Preview] Entrando a /preview")

    # 🔑 Validar token recibido en query o form
    token_arg = request.args.get('token') or request.form.get('token')
    token_session = session.get('token_admin')
    email = session.get('email')

    modo_admin = bool(session.get('modo_admin')) and token_arg and token_arg == token_session
    modo_admin_intentado = bool(token_arg)

    print(f"🔑 [Preview] modo_admin={modo_admin} modo_admin_intentado={modo_admin_intentado} token_arg={token_arg}")

    if not email:
        print("❌ [Preview] Sesión no iniciada")
        return "Error: sesión no iniciada", 403

    estilo_visual = session.get('estilo_visual')
    print(f"🎨 [Preview] email={email} estilo_visual={estilo_visual}")

    # Obtener productos desde Firestore
    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        for doc in productos_ref.stream():
            data = doc.to_dict()
            print(f"📄 [Preview] Doc ID={doc.id} Data={data}")
            productos.append(data)
        print(f"📊 [Preview] Productos obtenidos: {len(productos)}")
    except Exception as e:
        print("💥 [Preview] Error al leer productos:", e)
        productos = []

    # ✅ Ordenar por campo 'orden'
    productos = sorted(productos, key=lambda p: p.get('orden', 0))
    print("📊 [Preview] Orden de productos:", [p.get('orden') for p in productos])

    # ✅ Agrupar por grupo y subgrupo
    grupos_dict = {}
    for producto in productos:
        grupo = (producto.get('grupo') or 'General').strip().title()
        subgrupo = (producto.get('subgrupo') or 'Sin Subgrupo').strip().title()
        grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)

    print("📂 [Preview] Grupos generados:", {g: list(s.keys()) for g, s in grupos_dict.items()})

    # Credenciales de Mercado Pago
    mercado_pago_token = get_mp_token(email)
    public_key = get_mp_public_key(email) or ""
    print(f"💳 [Preview] email={email} mercado_pago_token={bool(mercado_pago_token)} public_key={public_key}")

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
        try:
            resultado = crear_repo_github(nombre_repo, token)
            print(f"📦 [Preview] Creando repo: {nombre_repo}, resultado={resultado}")
            if "url" in resultado:
                session['repo_creado'] = resultado["url"]
                session['repo_nombre'] = nombre_repo
        except Exception as e:
            print("💥 [Preview] Error al crear repo:", e)

    # Subir archivos si el repo existe
    if session.get('repo_creado') and session.get('repo_nombre'):
        nombre_repo = session['repo_nombre']
        token = os.getenv("GITHUB_TOKEN")
        if token:
            try:
                logo = config.get("logo")
                if logo:
                    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                    if os.path.exists(logo_path):
                        with open(logo_path, "rb") as f:
                            subir_archivo(nombre_repo, f.read(), f"static/img/{logo}")
                        print(f"✅ [Preview] Logo subido: {logo}")

                fondo = f"{estilo_visual}.jpeg"
                fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
                if os.path.exists(fondo_path):
                    with open(fondo_path, "rb") as f:
                        subir_archivo(nombre_repo, f.read(), f"static/img/{fondo}")
                    print(f"✅ [Preview] Fondo subido: {fondo}")
            except Exception as e:
                print("💥 [Preview] Error al subir archivos al repo:", e)

    try:
        print(f"🖼️ [Preview] Renderizando template preview.html con grupos: {grupos_dict}")
        return render_template(
            'preview.html',
            config=config,
            grupos=grupos_dict,
            modoAdmin=modo_admin,
            modoAdminIntentado=modo_admin_intentado,
            firebase_config=firebase_config
        )
    except Exception as e:
        print("💥 [Preview] Error al renderizar preview:", e)
        return "Internal Server Error al renderizar preview", 500

@app.route('/descargar')
def descargar():
    email = session.get('email')
    if not email:
        return "Error: sesión no iniciada", 403

    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    # Obtener productos del usuario
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        productos_docs = productos_ref.stream()
        productos = [doc.to_dict() for doc in productos_docs]
    except Exception as e:
        print(f"[DESCARGAR] Error leyendo productos: {e}")
        productos = []

    # Agrupar por grupo/subgrupo
    grupos = {}
    for producto in productos:
        grupo = (producto.get('grupo', 'General').strip().title())
        subgrupo = (producto.get('subgrupo', 'Sin subgrupo').strip().title())
        grupos.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)

    # Configuración visual
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

    # Renderizar HTML
    html = render_template('preview.html', config=config, grupos=grupos)

    # Crear ZIP en memoria
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('index.html', html)

        # Fondo
        fondo = f"{estilo_visual}.jpeg"
        fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
        if os.path.exists(fondo_path):
            zip_file.write(fondo_path, arcname='img/' + fondo)

        # Imágenes de productos
        for producto in productos:
            imagen_url = producto.get('imagen_github')
            if not imagen_url:
                continue

            if imagen_url.startswith("http"):  # caso GitHub raw_url
                try:
                    r = requests.get(imagen_url, timeout=10)
                    if r.status_code == 200:
                        filename = os.path.basename(imagen_url)
                        zip_file.writestr("img/" + filename, r.content)
                        print(f"✅ [DESCARGAR] Imagen incluida desde GitHub: {filename}")
                except Exception as e:
                    print(f"⚠️ [DESCARGAR] Error descargando {imagen_url}: {e}")
            else:  # fallback local
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(imagen_url))
                if os.path.exists(imagen_path):
                    zip_file.write(imagen_path, arcname="img/" + os.path.basename(imagen_url))
                    print(f"✅ [DESCARGAR] Imagen incluida desde local: {imagen_url}")

        # Logo
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
    limpiar_imagenes_usuario()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
