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
import smtplib
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from urllib.parse import urlencode, quote, unquote
##################
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
###################
# Verificación final del cliente Firestore
if db:
    try:
        test_doc = db.collection("_debug").document("conexion").get()
        print(f"[Firebase] Conexión Firestore OK, doc.exists={test_doc.exists}")
    except Exception as e:
        print("💥 Error verificando conexión Firestore:", e)
else:
    print("⚠️ Firestore client no disponible (db=None)")

####################
# 🔑 Inicialización segura de Mercado Pago
access_token = os.getenv("MERCADO_PAGO_TOKEN")
if access_token and isinstance(access_token, str):
    sdk = mercadopago.SDK(access_token.strip())
    print("✅ SDK de Mercado Pago inicializado globalmente")
else:
    sdk = None
    print("⚠️ MERCADO_PAGO_TOKEN no configurado, SDK no inicializado")
####################
# Configuración de GitHub, Flask y sesiones
token = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "jarafer96-byte"
ACCESS_TOKEN = os.getenv("WHATSAPP_TOKEN")

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024 
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "clave-secreta-temporal"
app.config['SESSION_COOKIE_SECURE'] = not app.debug

# Mantener las sesiones persistentes por defecto y duración
app.config['SESSION_PERMANENT'] = True
app.permanent_session_lifetime = timedelta(days=7)
###################
# 🔧 Configuración de Firebase Frontend (si se usa en JS)
firebase_config = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
}
###################
# Inicialización de Google Cloud Storage
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
###################
# Configuración de subida de imágenes
UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_IMAGE_SIZE_BYTES = 3 * 1024 * 1024
###################
# Generación de referencia corta (sirve para IDs temporales)
ext_ref = shortuuid.uuid()[:8]
###################
# Carga alternativa de credenciales (si se usa otra variable de entorno)
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
###################
# Configuración de Gmail API
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Validación de archivos permitidos
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def subir_a_firestore(producto, email):
    try:
        print(f"[FIRESTORE] 🚀 Iniciando subida de producto para email={email}")
        print(f"[FIRESTORE] Datos recibidos: {producto}")

        if not isinstance(producto, dict):
            print("[FIRESTORE] ❌ Producto inválido (no es dict)")
            return {"status": "error", "error": "Producto inválido (no es dict)"}

        if not producto.get("nombre") or not producto.get("grupo") or not producto.get("precio"):
            print("[FIRESTORE] ❌ Faltan campos obligatorios: nombre/grupo/precio")
            return {"status": "error", "error": "Faltan campos obligatorios: nombre/grupo/precio"}

        grupo_original = producto["grupo"].strip()
        subgrupo_original = (producto.get("subgrupo", "") or "").strip() or f"General_{grupo_original}"
        nombre_original = producto["nombre"].strip()
        print(f"[FIRESTORE] Campos normalizados: nombre={nombre_original}, grupo={grupo_original}, subgrupo={subgrupo_original}")

        nombre_id = nombre_original.replace(" ", "_").lower()
        subgrupo_id = subgrupo_original.replace(" ", "_").lower()
        fecha = time.strftime("%Y%m%d")
        sufijo = uuid.uuid4().hex[:6]
        custom_id = f"{nombre_id}_{fecha}_{subgrupo_id}_{sufijo}"
        print(f"[FIRESTORE] ID generado (id_base): {custom_id}")

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
            return {"status": "error", "error": f"Formato de precio inválido: '{price_str}' -> '{price_clean}'", "detail": str(e)}

        try:
            orden = int(producto.get("orden", 999))
        except Exception:
            orden = 999
        print(f"[FIRESTORE] Orden final: {orden}")

        # 👇 PARSEO MEJORADO DE TALLES Y COLORES
        talles = producto.get("talles") or []
        if isinstance(talles, str):
            talles = [t.strip() for t in talles.split(',') if t.strip()]
        
        colores = producto.get("colores") or []
        if isinstance(colores, str):
            colores = [c.strip() for c in colores.split(',') if c.strip()]
        
        print(f"[FIRESTORE] Talles procesados: {talles}")
        print(f"[FIRESTORE] Colores procesados: {colores}")

        # 👇 PARSEO MEJORADO DE STOCK GENERAL
        stock_raw = producto.get("stock")
        print(f"[FIRESTORE] Stock recibido (raw): {stock_raw}, tipo: {type(stock_raw)}")
        
        stock_general = 0  # default
        if stock_raw is not None:
            try:
                # Si es string, convertir a int
                if isinstance(stock_raw, str):
                    stock_raw = stock_raw.strip()
                    if stock_raw == "":
                        stock_general = 0
                    else:
                        stock_general = int(stock_raw)
                # Si ya es int o float
                elif isinstance(stock_raw, (int, float)):
                    stock_general = int(stock_raw)
                
                # Validar que no sea negativo
                if stock_general < 0:
                    stock_general = 0
                    print(f"[FIRESTORE] ⚠️ Stock negativo ajustado a 0")
                    
            except (ValueError, TypeError) as e:
                print(f"[FIRESTORE] ⚠️ Error parseando stock '{stock_raw}': {e}, usando default 0")
                stock_general = 0
        else:
            print(f"[FIRESTORE] ℹ️ Stock no proporcionado, usando default 0")
        
        print(f"[FIRESTORE] ✅ Stock general final: {stock_general}")

        # 👇 NUEVO: PROCESAR VARIANTES
        variantes = {}
        variantes_raw = producto.get("variantes") or {}
        
        # Bandera para saber si el producto usa variantes
        usar_variantes = False
        
        if isinstance(variantes_raw, dict) and variantes_raw:
            print(f"[FIRESTORE] Procesando {len(variantes_raw)} variantes explícitas")
            usar_variantes = True
            
            for key, variante in variantes_raw.items():
                try:
                    variante_stock = variante.get("stock", 0)
                    if isinstance(variante_stock, str):
                        variante_stock = int(variante_stock.strip() or 0)
                    
                    variantes[key] = {
                        "talle": variante.get("talle", ""),
                        "color": variante.get("color", ""),
                        "stock": max(0, variante_stock),
                        "imagen_url": variante.get("imagen_url", "")
                    }
                    print(f"[FIRESTORE] Variante '{key}': talle={variantes[key]['talle']}, color={variantes[key]['color']}, stock={variantes[key]['stock']}")
                except Exception as e:
                    print(f"[FIRESTORE] ⚠️ Error procesando variante {key}: {e}")
        
        # Si no hay variantes explícitas pero hay talles y colores, crear variantes automáticamente
        elif talles and colores:
            print(f"[FIRESTORE] Creando variantes automáticamente de talles x colores")
            usar_variantes = True
            
            # Distribuir stock equitativamente entre variantes
            num_variantes = len(talles) * len(colores)
            if num_variantes > 0:
                # Si hay stock general, distribuir equitativamente
                stock_por_variante = stock_general // num_variantes
                print(f"[FIRESTORE] Distribuyendo stock {stock_general} entre {num_variantes} variantes = {stock_por_variante} cada una")
                
                for talle in talles:
                    for color in colores:
                        key = f"{talle}_{color}".replace(" ", "_")
                        variantes[key] = {
                            "talle": talle,
                            "color": color,
                            "stock": stock_por_variante,
                            "imagen_url": ""
                        }
                print(f"[FIRESTORE] ✅ Creadas {len(variantes)} variantes automáticamente")
            else:
                print(f"[FIRESTORE] ⚠️ No se pueden crear variantes: talles={len(talles)}, colores={len(colores)}")

        # Calcular stock total basado en variantes si las hay
        if usar_variantes and variantes:
            stock_total = sum(v.get('stock', 0) for v in variantes.values())
            print(f"[FIRESTORE] ✅ Stock total calculado de variantes: {stock_total}")
        else:
            stock_total = stock_general
            print(f"[FIRESTORE] ✅ Usando stock general: {stock_total}")

        producto["id_base"] = custom_id

        # Imagen: usar la URL real si ya viene del upload, si no, fallback a custom_id.webp
        imagen_url = producto.get("imagen_url")
        if imagen_url:
            print(f"[FIRESTORE] Usando imagen_url provista: {imagen_url}")
        else:
            imagen_nombre = f"{custom_id}.webp"
            email_encoded = email.replace("@", "%40")
            imagen_url = f"https://storage.googleapis.com/mpagina/{email_encoded}/{imagen_nombre}"
            print(f"[FIRESTORE] Generada imagen_url por fallback: {imagen_url}")

        doc = {
            "nombre": nombre_original,
            "id_base": custom_id,
            "precio": precio,
            "stock": stock_total,  # Stock total (suma de variantes si aplica)
            "grupo": grupo_original,
            "subgrupo": subgrupo_original,
            "descripcion": producto.get("descripcion", ""),
            "imagen_url": imagen_url,
            "orden": orden,
            "talles": talles,  # Mantener para compatibilidad
            "colores": colores,  # Lista de colores
            "variantes": variantes,  # Estructura de variantes
            "tiene_variantes": usar_variantes,  # Flag para saber si usa variantes
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        print(f"[FIRESTORE] Documento a guardar: {doc}")

        ruta = f"usuarios/{email}/productos/{custom_id}"
        print(f"[FIRESTORE] Guardando en ruta: {ruta}")
        db.collection("usuarios").document(email).collection("productos").document(custom_id).set(doc)
        print(f"[FIRESTORE] ✅ Producto guardado correctamente en Firestore: {custom_id} para {email}")

        return {"status": "ok", "ok": True, "id_base": custom_id, "tiene_variantes": usar_variantes}

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[FIRESTORE] ❌ Error general al subir producto para {email}: {e}\n{tb}")
        return {"status": "error", "error": str(e), "trace": tb}

@app.route("/authorize")
def authorize():
    flow = build_flow()
    auth_url, _ = flow.authorization_url(prompt="consent")
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    print("\n[OAUTH] 📥 Callback recibido con URL:", request.url)
    try:
        flow = build_flow()
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        print("[OAUTH] ✅ Token obtenido correctamente")

        # Guardar token en Firestore
        token_data = creds.to_json()
        print("[OAUTH] 📦 Token JSON generado:", token_data[:80], "...")  # mostramos solo el inicio por seguridad

        db.collection("_tokens").document("gmail").set({
            "token": token_data,
            "actualizado": firestore.SERVER_TIMESTAMP
        })
        print("[OAUTH] ✅ Token guardado en Firestore (_tokens/gmail)")

        return "✅ Autorización completada y token guardado en Firestore"

    except Exception as e:
        tb = traceback.format_exc()
        print("[OAUTH] ❌ Error en oauth2callback:", e)
        print(tb)
        return "❌ Error en oauth2callback", 500


def get_gmail_service():
    print("\n[GMAIL] 🔎 Intentando recuperar token desde Firestore...")
    doc = db.collection("_tokens").document("gmail").get()
    if not doc.exists:
        print("[GMAIL] ❌ No se encontró token en Firestore")
        raise RuntimeError("No hay token guardado en Firestore")

    creds_json = doc.to_dict()["token"]
    print("[GMAIL] 📦 Token recuperado de Firestore:", creds_json[:80], "...")  # mostramos solo el inicio

    creds = Credentials.from_authorized_user_info(json.loads(creds_json), SCOPES)
    print("[GMAIL] ✅ Cliente Gmail inicializado correctamente")
    return build("gmail", "v1", credentials=creds)
    
def build_flow():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    flow = Flow.from_client_config(
        creds_dict,
        scopes=SCOPES,
        redirect_uri="https://mpagina.onrender.com/oauth2callback"
    )
    return flow   
    
@app.route("/img/<short_id>")
def redirect_image(short_id):
    # Buscar la URL larga en Firestore
    doc = db.collection("short_links").document(short_id).get()
    if doc.exists:
        url_larga = doc.to_dict().get("url")
        return redirect(url_larga)
    else:
        return "Link no encontrado", 404
        
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
        print("\n[SUBIR_FOTO] 🚀 Nueva petición recibida")

        # 1) Obtener archivo y email
        file = request.files.get("file")
        email = request.form.get("email")
        print(f"[SUBIR_FOTO] file={file}, email={email}")

        if not file or not email:
            print("[SUBIR_FOTO] ❌ Falta archivo o email")
            return jsonify({"ok": False, "error": "Falta archivo o email"}), 400

        # 2) Validar extensión
        if not allowed_file(file.filename):
            print(f"[SUBIR_FOTO] ❌ Formato inválido: {file.filename}")
            return jsonify({"ok": False, "error": "Formato inválido. Usa png/jpg/jpeg/webp"}), 400

        # 3) Validar tamaño
        file.seek(0, 2)  # ir al final
        size = file.tell()
        file.seek(0)     # volver al inicio
        print(f"[SUBIR_FOTO] Tamaño recibido: {size} bytes")

        if size > MAX_IMAGE_SIZE_BYTES:
            print(f"[SUBIR_FOTO] ❌ Imagen excede límite ({size} > {MAX_IMAGE_SIZE_BYTES})")
            return jsonify({"ok": False, "error": "Imagen excede 3 MB"}), 413

        # 4) Nombre seguro y único
        original_name = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{original_name}"
        print(f"[SUBIR_FOTO] Nombre final: {filename}")

        # 5) Ruta organizada por email
        email_path = email.replace("@", "_at_").replace(".", "_dot_")
        blob_path = f"usuarios/{email_path}/imagenes/{filename}"
        print(f"[SUBIR_FOTO] Blob path: {blob_path}")

        # 6) Subir al bucket
        blob = bucket.blob(blob_path)
        print(f"[SUBIR_FOTO] Subiendo al bucket={bucket.name}, content_type={file.content_type}")
        blob.upload_from_file(file, content_type=file.content_type or "image/jpeg")

        # 7) URL pública (sin make_public si UBLA activo)
        public_url = f"https://storage.googleapis.com/{bucket.name}/{blob_path}"
        print(f"[SUBIR_FOTO] ✅ Upload exitoso → URL={public_url}")

        return jsonify({"ok": True, "url": public_url, "path": blob_path, "size": size})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("[SUBIR_FOTO] 💥 Error inesperado:", e)
        print("[SUBIR_FOTO][TRACEBACK]\n", tb)
        return jsonify({"ok": False, "error": str(e), "trace": tb}), 500
        
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
            
            # Calcular stock disponible si tiene variantes
            stock_disponible = data.get("stock", 0)
            variantes = data.get("variantes", {})
            
            if variantes:
                # Si tiene variantes, calcular stock total sumando todas las variantes
                stock_total_variantes = sum(v.get('stock', 0) for v in variantes.values())
                stock_disponible = stock_total_variantes
            
            productos.append({
                "id": doc.id,
                "id_base": data.get("id_base"),
                "nombre": data.get("nombre"),
                "precio": data.get("precio"),
                "stock": stock_disponible,  # Stock total (suma de variantes si aplica)
                "grupo": data.get("grupo"),
                "subgrupo": data.get("subgrupo"),
                "descripcion": data.get("descripcion"),
                "imagen_url": data.get("imagen_url"),
                "orden": data.get("orden"),
                "talles": data.get("talles", []),
                "colores": data.get("colores", []),  # 👈 NUEVO
                "variantes": data.get("variantes", {}),  # 👈 NUEVO
                "tiene_variantes": data.get("tiene_variantes", False),  # 👈 NUEVO
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

@app.route('/success')
def pago_success():
    orden_id = request.args.get('orden_id')
    url_retorno = request.args.get('retorno')
    email_vendedor = request.args.get('email')
    
    print(f"[SUCCESS] ✅ Pago aprobado para orden: {orden_id}")
    print(f"[SUCCESS] 📍 URL de retorno: {url_retorno}")
    print(f"[SUCCESS] 👤 Email vendedor: {email_vendedor}")
    
    if url_retorno:
        try:
            url_retorno_decoded = unquote(url_retorno)  # 👈 CAMBIADO: solo unquote()
            params = f"pago=success&orden_id={orden_id}"
            if email_vendedor:
                params += f"&email={email_vendedor}"
            
            separator = '&' if '?' in url_retorno_decoded else '?'
            redirect_url = f"{url_retorno_decoded}{separator}{params}"
            
            print(f"[SUCCESS] ➡️ Redirigiendo a: {redirect_url}")
            return redirect(redirect_url)
        except Exception as e:
            print(f"[SUCCESS] ❌ Error procesando URL de retorno: {e}")
    
    if email_vendedor:
        return redirect(f"/preview?email={email_vendedor}&pago=success&orden_id={orden_id}")
    
    return "✅ Pago aprobado correctamente. ¡Gracias por tu compra!"

@app.route('/failure')
def failure():
    orden_id = request.args.get('orden_id')
    url_retorno = request.args.get('retorno')
    email_vendedor = request.args.get('email')
    
    print(f"[FAILURE] ❌ Pago fallido para orden: {orden_id}")
    print(f"[FAILURE] 📍 URL de retorno: {url_retorno}")
    print(f"[FAILURE] 👤 Email vendedor: {email_vendedor}")
    
    if url_retorno:
        try:
            url_retorno_decoded = unquote(url_retorno)  # 👈 CAMBIADO: solo unquote()
            params = f"pago=failure&orden_id={orden_id}"
            if email_vendedor:
                params += f"&email={email_vendedor}"
            
            separator = '&' if '?' in url_retorno_decoded else '?'
            redirect_url = f"{url_retorno_decoded}{separator}{params}"
            
            print(f"[FAILURE] ➡️ Redirigiendo a: {redirect_url}")
            return redirect(redirect_url)
        except Exception as e:
            print(f"[FAILURE] ❌ Error procesando URL de retorno: {e}")
    
    if email_vendedor:
        return redirect(f"/preview?email={email_vendedor}&pago=failure&orden_id={orden_id}")
    
    return redirect("/?pago_fallido=true")

@app.route('/pending')
def pending():
    orden_id = request.args.get('orden_id')
    url_retorno = request.args.get('retorno')
    email_vendedor = request.args.get('email')
    
    print(f"[PENDING] ⏳ Pago pendiente para orden: {orden_id}")
    print(f"[PENDING] 📍 URL de retorno: {url_retorno}")
    print(f"[PENDING] 👤 Email vendedor: {email_vendedor}")
    
    if url_retorno:
        try:
            url_retorno_decoded = unquote(url_retorno)  # 👈 CAMBIADO: solo unquote()
            params = f"pago=pending&orden_id={orden_id}"
            if email_vendedor:
                params += f"&email={email_vendedor}"
            
            separator = '&' if '?' in url_retorno_decoded else '?'
            redirect_url = f"{url_retorno_decoded}{separator}{params}"
            
            print(f"[PENDING] ➡️ Redirigiendo a: {redirect_url}")
            return redirect(redirect_url)
        except Exception as e:
            print(f"[PENDING] ❌ Error procesando URL de retorno: {e}")
    
    if email_vendedor:
        return redirect(f"/preview?email={email_vendedor}&pago=pending&orden_id={orden_id}")
    
    return redirect("/?pago_pendiente=true")
    
def log_event(tag, data):
    print(f"[{tag}] {data}")
    # opcional: guardar en Firestore o en un archivo de logs

def get_platform_token():
    token = os.environ.get("MERCADO_PAGO_TOKEN")
    print(f"[TOKEN] 🔑 Token de Mercado Pago obtenido: {'OK' if token else '❌ NO DEFINIDO'}")
    return token

@app.route("/comprobante/<orden_id>")
def comprobante(orden_id):
    """Renderizar comprobante con TODOS los datos unificados - VERSIÓN MEJORADA"""
    import json
    from datetime import datetime
    
    # Buscar en la colección global
    doc = db.collection("ordenes").document(orden_id).get()
    
    if not doc.exists:
        return "❌ Orden no encontrada", 404
    
    data = doc.to_dict()
    
    cliente_nombre = data.get("cliente_nombre", "Cliente").strip()
    cliente_email = data.get("cliente_email", "Sin email").strip()
    cliente_telefono = data.get("cliente_telefono", "Sin teléfono").strip()
    email_vendedor = data.get("email_vendedor")
    
    print(f"[COMPROBANTE] 🔍 Procesando orden {orden_id}")
    print(f"[COMPROBANTE] Cliente: {cliente_nombre}")
    print(f"[COMPROBANTE] Vendedor: {email_vendedor}")
    
    # Obtener productos usando la misma lógica que enviar_comprobante
    productos_data = data.get("carrito") or data.get("items") or data.get("items_mp") or []
    
    # Si productos_data es string, convertirlo a lista
    if isinstance(productos_data, str):
        try:
            productos_data = json.loads(productos_data)
        except:
            productos_data = []
            print(f"[COMPROBANTE] ⚠️ No se pudo convertir string a JSON")
    
    print(f"[COMPROBANTE] 📦 Productos encontrados: {len(productos_data)}")
    
    total = 0
    productos = []
    
    for idx, p in enumerate(productos_data):
        try:
            print(f"[COMPROBANTE] 🔍 Procesando producto {idx+1}:")
            
            # Verificar que sea un diccionario
            if not isinstance(p, dict):
                print(f"[COMPROBANTE] ⚠️ Producto no es diccionario: {type(p)}")
                continue
            
            # Extraer datos con múltiples intentos
            # 1. Buscar nombre/title
            nombre = p.get("title") or p.get("nombre") or p.get("name") or f"Producto {idx+1}"
            
            # 2. Buscar precio
            precio_raw = None
            for key in ["unit_price", "precio", "price", "unit_price"]:
                if key in p:
                    precio_raw = p[key]
                    break
            
            # Convertir precio a float
            precio = 0.0
            if precio_raw is not None:
                if isinstance(precio_raw, (int, float)):
                    precio = float(precio_raw)
                elif isinstance(precio_raw, str):
                    # Limpiar string: quitar $, comas, espacios
                    limpio = precio_raw.replace('$', '').replace(',', '.').strip()
                    try:
                        precio = float(limpio)
                    except:
                        print(f"[COMPROBANTE] ⚠️ No se pudo convertir precio: {precio_raw}")
                        precio = 0.0
            else:
                print(f"[COMPROBANTE] ⚠️ Precio no encontrado en producto")
            
            # 3. Buscar cantidad
            cantidad_raw = None
            for key in ["quantity", "cantidad", "qty"]:
                if key in p:
                    cantidad_raw = p[key]
                    break
            
            # Convertir cantidad a int
            cantidad = 1
            if cantidad_raw is not None:
                if isinstance(cantidad_raw, (int, float)):
                    cantidad = int(cantidad_raw)
                elif isinstance(cantidad_raw, str):
                    try:
                        cantidad = int(cantidad_raw)
                    except:
                        print(f"[COMPROBANTE] ⚠️ No se pudo convertir cantidad: {cantidad_raw}")
                        cantidad = 1
            else:
                print(f"[COMPROBANTE] ⚠️ Cantidad no encontrada, usando 1")
            
            # 4. Buscar talle
            talle = p.get("talle") or p.get("size") or ""
            
            # 5. Buscar imagen_url - MÉTODO MEJORADO
            imagen_url = None
            
            # Intentar múltiples fuentes para la imagen
            for key in ["imagen_url", "image_url", "picture_url", "img_url"]:
                if key in p and p[key]:
                    imagen_url = p[key]
                    break
            
            # Si no encontramos imagen en los datos del producto, buscar en Firestore
            if not imagen_url and email_vendedor:
                # Buscar por id_base
                id_base = p.get("id_base") or p.get("id") or p.get("product_id")
                if id_base:
                    try:
                        prod_doc = db.collection("usuarios").document(email_vendedor)\
                                      .collection("productos").document(id_base).get()
                        if prod_doc.exists:
                            prod_data = prod_doc.to_dict()
                            imagen_url = prod_data.get("imagen_url")
                            print(f"[COMPROBANTE] ✅ Imagen encontrada en Firestore: {imagen_url[:50] if imagen_url else 'None'}...")
                    except Exception as e:
                        print(f"[COMPROBANTE] ❌ Error buscando imagen en Firestore: {e}")
            
            # Si aún no hay imagen, intentar con nombre
            if not imagen_url and email_vendedor and nombre:
                try:
                    # Buscar producto por nombre (aproximado)
                    productos_ref = db.collection("usuarios").document(email_vendedor)\
                                      .collection("productos")
                    query = productos_ref.where("nombre", "==", nombre).limit(1).get()
                    if query:
                        prod_data = query[0].to_dict()
                        imagen_url = prod_data.get("imagen_url")
                        print(f"[COMPROBANTE] ✅ Imagen encontrada por nombre: {imagen_url[:50] if imagen_url else 'None'}...")
                except Exception as e:
                    print(f"[COMPROBANTE] ❌ Error buscando por nombre: {e}")
            
            # Optimizar imagen si es de Cloudinary o Firebase
            if imagen_url:
                # Cloudinary: optimizar a tamaño razonable
                if "cloudinary" in imagen_url or "res.cloudinary.com" in imagen_url:
                    if "/image/upload/" in imagen_url:
                        parts = imagen_url.split("/image/upload/")
                        if len(parts) == 2:
                            imagen_url = f"{parts[0]}/image/upload/w_300,h_180,c_fill/{parts[1]}"
                
                # Firebase Storage: agregar parámetro de tamaño
                elif "firebasestorage.googleapis.com" in imagen_url:
                    # Para Firebase, podemos usar parámetros de transformación si están habilitados
                    # O simplemente usar la URL base
                    imagen_url = f"{imagen_url}?alt=media"
            
            # Calcular subtotal
            subtotal = precio * cantidad
            total += subtotal
            
            producto = {
                "nombre": nombre,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": subtotal,
                "imagen_url": imagen_url,
                "talle": talle
            }
            
            productos.append(producto)
            
            print(f"[COMPROBANTE]   ✓ {nombre}")
            print(f"      Precio: ${precio:.2f}")
            print(f"      Cantidad: {cantidad}")
            print(f"      Subtotal: ${subtotal:.2f}")
            print(f"      Talle: {talle}")
            print(f"      Imagen: {imagen_url[:50]}..." if imagen_url else "      Imagen: No")
            
        except Exception as e:
            print(f"[COMPROBANTE] ❌ Error procesando producto {idx+1}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Usar el total de la orden si lo tenemos, o usar el calculado
    orden_total = data.get("total")
    if orden_total:
        try:
            total = float(orden_total)
            print(f"[COMPROBANTE] 💰 Usando total de orden: ${total:.2f}")
        except Exception as e:
            print(f"[COMPROBANTE] ⚠️ No se pudo convertir total de orden: {orden_total}, usando calculado")
    else:
        print(f"[COMPROBANTE] 💰 Total calculado: ${total:.2f}")
    
    # Verificar si hay productos procesados
    if len(productos) == 0:
        print(f"[COMPROBANTE] ⚠️ No se procesaron productos, usando datos mínimos")
        productos.append({
            "nombre": "Productos varios",
            "cantidad": 1,
            "precio": total if total > 0 else 1.0,
            "subtotal": total if total > 0 else 1.0,
            "imagen_url": "",
            "talle": ""
        })
    
    # Obtener fecha
    fecha_creacion = data.get("fecha_creacion") or data.get("timestamp") or datetime.now()
    if isinstance(fecha_creacion, datetime):
        fecha_str = fecha_creacion.strftime("%d/%m/%Y %H:%M")
    else:
        fecha_str = str(fecha_creacion)
    
    print(f"[COMPROBANTE] ✅ Total productos procesados: {len(productos)}")
    print(f"[COMPROBANTE] ✅ Total: ${total:.2f}")
    
    return render_template("comprobante.html",
                          orden_id=orden_id,
                          cliente_nombre=cliente_nombre,
                          cliente_email=cliente_email,
                          cliente_telefono=cliente_telefono,
                          productos=productos,
                          total=total,
                          fecha=fecha_str)

# Enviar comprobante por correo - VERSIÓN MEJORADA
def enviar_comprobante(email_vendedor, orden_id):
    import json
    from datetime import datetime
    
    doc_ref = db.collection("ordenes").document(orden_id)
    doc = doc_ref.get()
    if not doc.exists:
        print(f"[EMAIL] ❌ No se encontró orden {orden_id}")
        return False

    data = doc.to_dict()

    # ⚠️ Evitar duplicados
    if data.get("comprobante_enviado"):
        print(f"[EMAIL] ⚠️ Comprobante ya enviado para orden {orden_id}")
        return True

    # Datos del cliente
    cliente_nombre = data.get("cliente_nombre", "Cliente").strip()
    cliente_email = data.get("cliente_email", "").strip()
    cliente_telefono = data.get("cliente_telefono", "No especificado").strip()
    
    # DEBUG: Ver qué datos tenemos
    print(f"[EMAIL] 📊 Datos de la orden {orden_id}:")
    print(f"  - Cliente: {cliente_nombre}")
    print(f"  - Total en data: {data.get('total')}")
    print(f"  - Tiene items_mp?: {'items_mp' in data}")
    print(f"  - Tiene items?: {'items' in data}")
    
    # Obtener productos - PRIMERO intentar con carrito (items completos)
    productos_data = data.get("carrito") or data.get("items") or data.get("items_mp") or []
    
    # Si productos_data es string, convertirlo a lista
    if isinstance(productos_data, str):
        try:
            productos_data = json.loads(productos_data)
        except:
            productos_data = []
            print(f"[EMAIL] ⚠️ No se pudo convertir string a JSON")
    
    print(f"[EMAIL] 📦 Productos encontrados (raw): {len(productos_data)}")
    
    total = 0
    productos_procesados = []
    
    for idx, p in enumerate(productos_data):
        try:
            print(f"[EMAIL] 🔍 Procesando producto {idx+1}:")
            
            # Verificar que sea un diccionario
            if not isinstance(p, dict):
                print(f"[EMAIL] ⚠️ Producto no es diccionario: {type(p)}")
                continue
            
            # DEBUG: Mostrar todas las claves del producto
            print(f"  - Claves disponibles: {list(p.keys())}")
            
            # Extraer datos con múltiples intentos (diferentes formatos)
            # 1. Buscar nombre/title
            nombre = p.get("title") or p.get("nombre") or p.get("name") or f"Producto {idx+1}"
            
            # 2. Buscar precio - con múltiples nombres posibles
            precio_raw = None
            for key in ["unit_price", "precio", "price", "unit_price"]:
                if key in p:
                    precio_raw = p[key]
                    break
            
            # Convertir precio a float
            precio = 0.0
            if precio_raw is not None:
                if isinstance(precio_raw, (int, float)):
                    precio = float(precio_raw)
                elif isinstance(precio_raw, str):
                    # Limpiar string: quitar $, comas, espacios
                    limpio = precio_raw.replace('$', '').replace(',', '.').strip()
                    try:
                        precio = float(limpio)
                    except:
                        print(f"[EMAIL] ⚠️ No se pudo convertir precio: {precio_raw}")
                        precio = 0.0
            else:
                print(f"[EMAIL] ⚠️ Precio no encontrado en producto")
            
            # 3. Buscar cantidad - con múltiples nombres posibles
            cantidad_raw = None
            for key in ["quantity", "cantidad", "qty"]:
                if key in p:
                    cantidad_raw = p[key]
                    break
            
            # Convertir cantidad a int
            cantidad = 1
            if cantidad_raw is not None:
                if isinstance(cantidad_raw, (int, float)):
                    cantidad = int(cantidad_raw)
                elif isinstance(cantidad_raw, str):
                    try:
                        cantidad = int(cantidad_raw)
                    except:
                        print(f"[EMAIL] ⚠️ No se pudo convertir cantidad: {cantidad_raw}")
                        cantidad = 1
            else:
                print(f"[EMAIL] ⚠️ Cantidad no encontrada, usando 1")
            
            # 4. Buscar talle
            talle = p.get("talle") or p.get("size") or ""
            
            # 5. Buscar imagen_url y procesar para tamaño 300x180
            imagen_url = p.get("imagen_url") or p.get("image_url") or ""
            
            # Si hay imagen_url, agregar parámetros para tamaño si no los tiene
            if imagen_url and ("?" not in imagen_url or ("width=" not in imagen_url and "height=" not in imagen_url)):
                # Dependiendo de tu servicio de imágenes, ajusta estos parámetros
                # Opción 1: Agregar parámetros de tamaño (si tu backend los soporta)
                if "cloudinary" in imagen_url or "res.cloudinary.com" in imagen_url:
                    # Cloudinary soporta parámetros de transformación
                    if "/image/upload/" in imagen_url:
                        parts = imagen_url.split("/image/upload/")
                        if len(parts) == 2:
                            imagen_url = f"{parts[0]}/image/upload/w_300,h_180,c_fill/{parts[1]}"
                elif "firebasestorage.googleapis.com" in imagen_url:
                    # Firebase Storage - agregar tamaño
                    imagen_url = f"{imagen_url}?alt=media"
            
            # Calcular subtotal
            subtotal = precio * cantidad
            total += subtotal
            
            producto_procesado = {
                "title": nombre,
                "unit_price": precio,
                "quantity": cantidad,
                "subtotal": subtotal,
                "talle": talle,
                "imagen_url": imagen_url
            }
            
            productos_procesados.append(producto_procesado)
            
            print(f"[EMAIL]   ✓ {nombre}")
            print(f"      Precio: ${precio:.2f} (raw: {precio_raw})")
            print(f"      Cantidad: {cantidad} (raw: {cantidad_raw})")
            print(f"      Subtotal: ${subtotal:.2f}")
            print(f"      Talle: {talle}")
            print(f"      Imagen: {imagen_url[:50]}..." if imagen_url else "      Imagen: No")
            
        except Exception as e:
            print(f"[EMAIL] ❌ Error procesando producto {idx+1}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Usar el total de la orden si lo tenemos, o usar el calculado
    orden_total = data.get("total")
    if orden_total:
        try:
            total = float(orden_total)
            print(f"[EMAIL] 💰 Usando total de orden: ${total:.2f}")
        except Exception as e:
            print(f"[EMAIL] ⚠️ No se pudo convertir total de orden: {orden_total}, usando calculado")
    else:
        print(f"[EMAIL] 💰 Total calculado: ${total:.2f}")
    
    # Verificar si hay productos procesados
    if len(productos_procesados) == 0:
        print(f"[EMAIL] ⚠️ No se procesaron productos, enviando datos mínimos")
        # Crear un producto mínimo para evitar errores en el template
        productos_procesados.append({
            "title": "Productos varios",
            "unit_price": total if total > 0 else 1.0,
            "quantity": 1,
            "subtotal": total if total > 0 else 1.0,
            "talle": "",
            "imagen_url": ""
        })
    
    # Link al comprobante
    comprobante_url = f"https://mpagina.onrender.com/comprobante/{orden_id}"
    
    # Obtener fecha
    fecha_creacion = data.get("fecha_creacion") or data.get("timestamp") or datetime.now()
    if isinstance(fecha_creacion, datetime):
        fecha_str = fecha_creacion.strftime("%d/%m/%Y %H:%M")
    else:
        fecha_str = str(fecha_creacion)

    try:
        service = get_gmail_service()
        
        # Renderizar el HTML
        html = render_template("comprobante_email.html",
                               cliente_nombre=cliente_nombre,
                               cliente_email=cliente_email,
                               cliente_telefono=cliente_telefono,
                               productos=productos_procesados,
                               total=total,
                               comprobante_url=comprobante_url,
                               orden_id=orden_id,
                               fecha_creacion=fecha_str)

        # Crear mensaje MIME
        msg = MIMEText(html, "html")
        msg["Subject"] = f"💰 Nueva venta - Orden #{orden_id} - ${total:.2f}"
        msg["From"] = "ferj6009@gmail.com"
        msg["To"] = email_vendedor
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        
        # Enviar email
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        
        print(f"[EMAIL] ✅ Comprobante enviado a {email_vendedor} - Orden #{orden_id}")
        print(f"[EMAIL] 📧 Productos incluidos: {len(productos_procesados)}")
        print(f"[EMAIL] 💵 Total: ${total:.2f}")
        
        # Marcar como enviado en Firestore
        doc_ref.update({
            "comprobante_enviado": True,
            "comprobante_enviado_fecha": firestore.SERVER_TIMESTAMP,
            "productos_procesados": productos_procesados,  # Guardar también los productos procesados
            "actualizado": firestore.SERVER_TIMESTAMP
        })
        
        return True
        
    except Exception as e:
        print(f"[EMAIL] ❌ Error enviando comprobante: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route("/webhook_mp", methods=["POST"])
def webhook_mp():
    """Webhook unificado - Versión ultra-robusta con soporte para variantes"""
    evento = request.get_json(force=True) or {}
    print(f"[WEBHOOK] 📥 Evento recibido")
    
    # Extraer payment_id
    payment_id = None
    if "data" in evento and isinstance(evento["data"], dict):
        payment_id = evento["data"].get("id")
    elif "id" in evento:
        payment_id = evento.get("id")
    
    if not payment_id:
        print("[WEBHOOK] ❌ No se encontró payment_id")
        return jsonify({"ok": False}), 400
    
    # Consultar detalle del pago
    access_token = os.getenv("MERCADO_PAGO_TOKEN")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        r = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", 
                        headers=headers, timeout=15)
        detalle = r.json()
        
        if r.status_code != 200:
            print(f"[WEBHOOK] ❌ Error consultando pago: {r.text}")
            return jsonify({"ok": False}), 500
        
        # ID CLAVE - DEBE SER EL MISMO QUE GUARDAMOS
        external_ref = detalle.get("external_reference")
        if not external_ref:
            print("[WEBHOOK] ❌ No external_reference en el pago")
            return jsonify({"ok": False}), 400
        
        estado = detalle.get("status")
        print(f"[WEBHOOK] 🔎 Orden: {external_ref}, Estado: {estado}")
        
        # Buscar en la colección global "ordenes"
        doc_ref = db.collection("ordenes").document(external_ref)
        doc = doc_ref.get()
        
        if not doc.exists:
            print(f"[WEBHOOK] ❌ Orden {external_ref} no encontrada en Firestore")
            return jsonify({"ok": False}), 404
        
        orden_data = doc.to_dict()
        
        # 👇 **VERSIÓN MEJORADA: Restar stock si el pago fue aprobado**
        if estado == "approved":
            email_vendedor = orden_data.get("email_vendedor")
            
            if email_vendedor:
                # ✅ CORRECCIÓN: USAR CARRITO EN LUGAR DE ITEMS_MP
                todos_items = orden_data.get("carrito") or []
                
                # Si carrito está vacío, intentar con items_mp
                if not todos_items:
                    todos_items = orden_data.get("items_mp") or orden_data.get("items") or []
                    print(f"[WEBHOOK-STOCK] ⚠️ Carrito vacío, usando items_mp/items")
                
                print(f"[WEBHOOK-STOCK] 📦 Items encontrados en carrito: {len(todos_items)}")
                
                for item in todos_items:
                    try:
                        if not isinstance(item, dict):
                            print(f"[WEBHOOK-STOCK] ⚠️ Item no es dict: {type(item)}")
                            continue
                            
                        # ✅ **BÚSQUEDA DE PRODUCTO_ID DESDE CARRITO**
                        producto_id = item.get("id_base")
                        
                        if not producto_id:
                            print(f"[WEBHOOK-STOCK] ⚠️ Item sin id_base: {item}")
                            continue
                        
                        # ✅ **BÚSQUEDA DE CANTIDAD DESDE CARRITO**
                        cantidad = int(item.get("cantidad", 1))
                        
                        # ✅ **BÚSQUEDA DE TALLE Y COLOR DESDE CARRITO**
                        talle = item.get("talle", "")
                        color = item.get("color", "")
                        
                        print(f"[WEBHOOK-STOCK] 🔍 Producto: {producto_id}, Talle: {talle}, Color: {color}, Cantidad: {cantidad}")
                        
                        # ✅ **DESCONTAR STOCK - CON SOPORTE PARA VARIANTES**
                        prod_ref = db.collection("usuarios").document(email_vendedor)\
                                      .collection("productos").document(producto_id)
                        prod_doc = prod_ref.get()
                        
                        if prod_doc.exists:
                            data = prod_doc.to_dict()
                            
                            # Verificar si el producto usa variantes
                            tiene_variantes = data.get("tiene_variantes", False)
                            variantes = data.get("variantes", {})
                            
                            if tiene_variantes and variantes and talle and color:
                                # 👇 DESCONTAR DE VARIANTE ESPECÍFICA
                                variante_key = f"{talle}_{color}".replace(" ", "_")
                                
                                if variante_key in variantes:
                                    variante = variantes[variante_key]
                                    stock_variante = variante.get("stock", 0)
                                    nuevo_stock_variante = max(0, stock_variante - cantidad)
                                    
                                    # Actualizar variante específica
                                    prod_ref.update({
                                        f"variantes.{variante_key}.stock": nuevo_stock_variante,
                                        "stock": firestore.Increment(-cantidad)  # Actualizar stock total
                                    })
                                    
                                    print(f"[WEBHOOK-STOCK] ✅ Variante {variante_key}: {stock_variante} → {nuevo_stock_variante} (-{cantidad})")
                                    
                                    # 🔄 Guardar histórico para variante
                                    historial_ref = db.collection("usuarios").document(email_vendedor)\
                                                       .collection("productos").document(producto_id)\
                                                       .collection("stock_historial").document(f"{external_ref}_{variante_key}")
                                    
                                    historial_ref.set({
                                        "orden_id": external_ref,
                                        "fecha": firestore.SERVER_TIMESTAMP,
                                        "stock_antes": stock_variante,
                                        "stock_despues": nuevo_stock_variante,
                                        "cantidad_descontada": cantidad,
                                        "payment_id": payment_id,
                                        "tipo": "compra_webhook_variante",
                                        "talle": talle,
                                        "color": color,
                                        "variante_key": variante_key,
                                        "nombre_producto": data.get("nombre", "")
                                    })
                                    
                                else:
                                    # Variante no encontrada, descontar del stock general
                                    print(f"[WEBHOOK-STOCK] ⚠️ Variante {variante_key} no encontrada, descontando del stock general")
                                    stock_actual = data.get("stock", 0)
                                    nuevo_stock = max(0, stock_actual - cantidad)
                                    prod_ref.update({"stock": nuevo_stock})
                                    print(f"[WEBHOOK-STOCK] ✅ Stock general: {stock_actual} → {nuevo_stock} (-{cantidad})")
                                    
                                    historial_ref = db.collection("usuarios").document(email_vendedor)\
                                                       .collection("productos").document(producto_id)\
                                                       .collection("stock_historial").document(external_ref)
                                    
                                    historial_ref.set({
                                        "orden_id": external_ref,
                                        "fecha": firestore.SERVER_TIMESTAMP,
                                        "stock_antes": stock_actual,
                                        "stock_despues": nuevo_stock,
                                        "cantidad_descontada": cantidad,
                                        "payment_id": payment_id,
                                        "tipo": "compra_webhook_general",
                                        "talle": talle,
                                        "color": color,
                                        "nombre_producto": data.get("nombre", "")
                                    })
                            else:
                                # Producto sin variantes, descontar del stock general
                                stock_actual = data.get("stock", 0)
                                nuevo_stock = max(0, stock_actual - cantidad)
                                prod_ref.update({"stock": nuevo_stock})
                                print(f"[WEBHOOK-STOCK] ✅ Stock general: {stock_actual} → {nuevo_stock} (-{cantidad})")
                                
                                historial_ref = db.collection("usuarios").document(email_vendedor)\
                                                   .collection("productos").document(producto_id)\
                                                   .collection("stock_historial").document(external_ref)
                                
                                historial_ref.set({
                                    "orden_id": external_ref,
                                    "fecha": firestore.SERVER_TIMESTAMP,
                                    "stock_antes": stock_actual,
                                    "stock_despues": nuevo_stock,
                                    "cantidad_descontada": cantidad,
                                    "payment_id": payment_id,
                                    "tipo": "compra_webhook",
                                    "talle": talle,
                                    "color": color,
                                    "nombre_producto": data.get("nombre", "")
                                })
                            
                        else:
                            print(f"[WEBHOOK-STOCK] ⚠️ Producto {producto_id} no encontrado en {email_vendedor}")
                            # Intentar buscar por nombre si no encontramos por ID
                            nombre_producto = item.get("nombre")
                            if nombre_producto:
                                print(f"[WEBHOOK-STOCK] 🔍 Intentando buscar por nombre: {nombre_producto}")
                                try:
                                    # Buscar producto por nombre
                                    query = db.collection("usuarios").document(email_vendedor)\
                                              .collection("productos").where("nombre", "==", nombre_producto).get()
                                    if query:
                                        for prod_doc in query:
                                            prod_data = prod_doc.to_dict()
                                            producto_id_real = prod_doc.id
                                            stock_actual_real = prod_data.get("stock", 0)
                                            nuevo_stock_real = max(0, stock_actual_real - cantidad)
                                            
                                            prod_doc.reference.update({"stock": nuevo_stock_real})
                                            print(f"[WEBHOOK-STOCK] ✅ Encontrado por nombre: {nombre_producto} -> {producto_id_real}: {stock_actual_real} → {nuevo_stock_real}")
                                            break
                                except Exception as e:
                                    print(f"[WEBHOOK-STOCK] ❌ Error buscando producto por nombre: {e}")
                            
                    except Exception as e:
                        print(f"[WEBHOOK-STOCK] ❌ Error procesando item: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
        
        # Actualizar estado del pago
        update_data = {
            "estado": estado,
            "payment_id": payment_id,
            "actualizado": firestore.SERVER_TIMESTAMP,
            "webhook_processed": True,
            "webhook_timestamp": firestore.SERVER_TIMESTAMP,
            "stock_actualizado": estado == "approved",
        }
        
        if estado == "approved":
            update_data["stock_actualizado_fecha"] = firestore.SERVER_TIMESTAMP
        
        doc_ref.update(update_data)
        
        # Si el pago fue aprobado, enviar comprobante
        if estado == "approved":
            email_vendedor = orden_data.get("email_vendedor")
            
            if email_vendedor:
                # Verificar si ya se envió comprobante
                if not orden_data.get("comprobante_enviado", False):
                    enviar_comprobante(email_vendedor, external_ref)
                    print(f"[WEBHOOK] ✅ Comprobante enviado para orden {external_ref}")
                else:
                    print(f"[WEBHOOK] ⚠️ Comprobante ya enviado anteriormente para {external_ref}")
        
        return jsonify({"ok": True})
        
    except Exception as e:
        print(f"[WEBHOOK] ❌ Error procesando webhook: {e}")
        traceback.print_exc()
        return jsonify({"ok": False}), 500

# Agrega esto después de las rutas existentes

@app.route('/api/variantes/<producto_id>', methods=['GET'])
def get_variantes(producto_id):
    """Obtener todas las variantes de un producto"""
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Falta email'}), 400
    
    try:
        doc = db.collection("usuarios").document(email)\
               .collection("productos").document(producto_id).get()
        
        if not doc.exists:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        data = doc.to_dict()
        
        # Calcular stock total si es necesario
        variantes = data.get('variantes', {})
        stock_total = sum(v.get('stock', 0) for v in variantes.values())
        
        return jsonify({
            'variantes': variantes,
            'talles': data.get('talles', []),
            'colores': data.get('colores', []),
            'tiene_variantes': data.get('tiene_variantes', False),
            'stock_total': stock_total,
            'nombre': data.get('nombre', '')
        })
        
    except Exception as e:
        print(f"[API-VARIANTES] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/variantes/<producto_id>/actualizar', methods=['POST'])
def actualizar_variante(producto_id):
    """Actualizar stock de una variante específica"""
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    variante_key = data.get('variante_key')
    nuevo_stock = data.get('stock')
    
    if not email or not variante_key or nuevo_stock is None:
        return jsonify({'error': 'Datos incompletos'}), 400
    
    try:
        # Convertir stock a entero
        nuevo_stock_int = int(nuevo_stock)
        if nuevo_stock_int < 0:
            return jsonify({'error': 'Stock no puede ser negativo'}), 400
        
        doc_ref = db.collection("usuarios").document(email)\
                    .collection("productos").document(producto_id)
        
        # Actualizar stock de la variante
        doc_ref.update({
            f"variantes.{variante_key}.stock": nuevo_stock_int,
            "actualizado": firestore.SERVER_TIMESTAMP
        })
        
        # Recalcular stock total
        doc = doc_ref.get()
        if doc.exists:
            data_doc = doc.to_dict()
            variantes = data_doc.get('variantes', {})
            stock_total = sum(v.get('stock', 0) for v in variantes.values())
            doc_ref.update({"stock": stock_total})
        
        print(f"[VARIANTES] ✅ Variante actualizada: {producto_id}/{variante_key} -> {nuevo_stock_int}")
        return jsonify({'status': 'ok', 'stock_total': stock_total})
        
    except Exception as e:
        print(f"[VARIANTES] ❌ Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/productos/<producto_id>/stock-variantes', methods=['GET'])
def get_stock_variantes(producto_id):
    """Obtener stock por variante para un producto específico"""
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Falta email'}), 400
    
    try:
        doc = db.collection("usuarios").document(email)\
               .collection("productos").document(producto_id).get()
        
        if not doc.exists:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        data = doc.to_dict()
        variantes = data.get('variantes', {})
        
        # Formatear respuesta para fácil uso en frontend
        stock_por_variante = {}
        for key, variante in variantes.items():
            stock_por_variante[key] = {
                'stock': variante.get('stock', 0),
                'talle': variante.get('talle', ''),
                'color': variante.get('color', ''),
                'disponible': variante.get('stock', 0) > 0
            }
        
        return jsonify({
            'stock_por_variante': stock_por_variante,
            'talles_disponibles': data.get('talles', []),
            'colores_disponibles': data.get('colores', []),
            'tiene_variantes': data.get('tiene_variantes', False),
            'nombre': data.get('nombre', '')
        })
        
    except Exception as e:
        print(f"[STOCK-VARIANTES] Error: {e}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/pagar', methods=['POST'])
def pagar():
    print("\n🚀 [PAGAR UNIFICADO] Nueva petición recibida")
    
    if not db:
        return jsonify({'error': 'Firestore no disponible'}), 503

    try:
        data = request.get_json(silent=True) or {}
        print(f"[PAGAR] Datos recibidos: {json.dumps(data, indent=2)}")
        
        # 1. Recibir TODOS los datos del frontend
        carrito = data.get('carrito', [])
        items_mp = data.get('items_mp', [])
        email_vendedor = data.get('email_vendedor')
        numero_vendedor = data.get('numero_vendedor', '')
        cliente_nombre = data.get('cliente_nombre')
        cliente_email = data.get('cliente_email')
        cliente_telefono = data.get('cliente_telefono', '')
        orden_id = data.get('orden_id')
        total_recibido = data.get('total', 0)
        url_retorno = data.get('url_retorno')
        
        print(f"[PAGAR] 📊 Resumen de datos:")
        print(f"  - Email vendedor: {email_vendedor}")
        print(f"  - Cliente: {cliente_nombre}")
        print(f"  - Carrito recibido: {len(carrito)} items")
        print(f"  - Items_MP recibido: {len(items_mp)} items")
        print(f"  - Total recibido: ${total_recibido}")
        print(f"  - Orden ID recibido: {orden_id}")
        print(f"  - URL retorno (usuario): {url_retorno}")
        
        if not email_vendedor:
            return jsonify({'error': 'Falta email del vendedor'}), 400
        
        if not carrito and not items_mp:
            return jsonify({'error': 'Carrito vacío'}), 400
        
        # 2. Generar ID único
        if orden_id and orden_id.strip() and orden_id.startswith('ORD_'):
            external_ref = orden_id.strip()
            print(f"[PAGAR] ✅ Usando orden_id proporcionado: {external_ref}")
        else:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            external_ref = f"ORD_{timestamp}_{shortuuid.uuid()[:8]}"
            print(f"[PAGAR] ⚠️ No se recibió orden_id válido, se generó: {external_ref}")
        
        # 3. Obtener token de Mercado Pago DEL VENDEDOR
        access_token = get_mp_token(email_vendedor)
        if not access_token or not isinstance(access_token, str):
            print(f"[PAGAR] ❌ Token inválido para vendedor: {email_vendedor}")
            return jsonify({'error': 'Vendedor sin credenciales MP válidas'}), 400
        
        sdk = mercadopago.SDK(access_token.strip())
        
        # 4. Preparar items para Mercado Pago
        if items_mp and len(items_mp) > 0:
            print(f"[PAGAR] ✅ Usando items_mp proporcionados del frontend")
            items_para_mp = items_mp
            
            # 🔥 CORRECCIÓN: Asegurar que items_mp tengan "id" si vienen del frontend
            for item in items_para_mp:
                if not item.get('id') and not item.get('id_base'):
                    # Buscar en el carrito por título o nombre
                    titulo_item = item.get('title', '')
                    for item_carrito in carrito:
                        nombre_carrito = item_carrito.get('nombre', '')
                        if nombre_carrito and titulo_item and nombre_carrito in titulo_item:
                            item['id'] = item_carrito.get('id_base', '')
                            item['id_base'] = item_carrito.get('id_base', '')
                            print(f"[PAGAR] 🔄 Agregado id_base a item MP: {item['id']}")
                            break
        else:
            print(f"[PAGAR] 🔄 Convirtiendo carrito a formato MP")
            items_para_mp = []
            for item in carrito:
                try:
                    precio = item.get('precio', 0)
                    if isinstance(precio, str):
                        precio = float(precio.replace('$', '').replace(',', '.').strip())
                    else:
                        precio = float(precio)
                    
                    cantidad = int(item.get('cantidad', 1))
                    nombre = item.get('nombre', 'Producto')
                    talle = item.get('talle', '')
                    id_base = item.get('id_base', '')
                    
                    titulo = nombre if not talle else f"{nombre} (Talle: {talle})"
                    
                    # 🔥 CORRECCIÓN COMPLETA: Incluir TODOS los campos necesarios
                    item_mp = {
                        "id": id_base,  # ✅ Campo CRÍTICO para el webhook
                        "id_base": id_base,  # ✅ Campo adicional
                        "title": titulo,
                        "description": nombre,
                        "quantity": cantidad,
                        "unit_price": precio,
                        "currency_id": "ARS"
                    }
                    
                    # Si no hay id_base, generamos uno temporal
                    if not id_base:
                        item_mp["id"] = f"temp_{uuid.uuid4().hex[:8]}"
                        item_mp["id_base"] = item_mp["id"]
                        print(f"[PAGAR] ⚠️ Item sin id_base, usando temporal: {item_mp['id']}")
                    
                    items_para_mp.append(item_mp)
                    
                    print(f"  - Convertido: {nombre} - ${precio} x {cantidad} | id_base: {id_base}")
                except Exception as e:
                    print(f"  - ❌ Error convirtiendo item: {e}")
                    continue
        
        # Validar que los items tengan "id" (requerido para el webhook)
        items_sin_id = [item for item in items_para_mp if not item.get('id')]
        if items_sin_id:
            print(f"[PAGAR] ⚠️ Items sin 'id': {len(items_sin_id)}")
            for i, item in enumerate(items_sin_id):
                # Generar ID temporal
                temp_id = f"temp_{external_ref}_{i}"
                item['id'] = temp_id
                item['id_base'] = temp_id
                print(f"[PAGAR] 🔄 Asignado ID temporal: {temp_id}")
        
        if not items_para_mp:
            return jsonify({'error': 'No se pudieron procesar los productos para el pago'}), 400
        
        print(f"[PAGAR] 📦 Items para Mercado Pago ({len(items_para_mp)}):")
        for idx, item in enumerate(items_para_mp):
            print(f"  {idx+1}. {item.get('title')} - ${item.get('unit_price')} x {item.get('quantity')} | id: {item.get('id')}")
        
        # 5. Calcular total
        total_calculado = sum(item.get('unit_price', 0) * item.get('quantity', 1) for item in items_para_mp)
        print(f"[PAGAR] 💰 Total calculado: ${total_calculado:.2f}")
        print(f"[PAGAR] 💰 Total recibido: ${total_recibido}")
        
        total_final = max(total_calculado, float(total_recibido or 0))
        print(f"[PAGAR] 💰 Total final a usar: ${total_final:.2f}")
        
        # 6. Crear preferencia con back_urls a TU backend
        base_url = "https://mpagina.onrender.com"
        
        # Usar url_retorno para pasar como parámetro, no como base
        url_retorno_encoded = quote(url_retorno or "", safe='')
        
        preference_data = {
            "items": items_para_mp,
            "back_urls": {
                "success": f"{base_url}/success?orden_id={external_ref}&retorno={url_retorno_encoded}&email={email_vendedor}",
                "failure": f"{base_url}/failure?orden_id={external_ref}&retorno={url_retorno_encoded}&email={email_vendedor}",
                "pending": f"{base_url}/pending?orden_id={external_ref}&retorno={url_retorno_encoded}&email={email_vendedor}"
            },
            "auto_return": "approved",
            "external_reference": external_ref,
            "notification_url": f"{base_url}/webhook_mp",
            "metadata": {
                "email_vendedor": email_vendedor,
                "numero_vendedor": numero_vendedor,
                "cliente_nombre": cliente_nombre,
                "cliente_email": cliente_email,
                "cliente_telefono": cliente_telefono,
                "url_retorno": url_retorno
            }
        }
        
        print(f"[PAGAR] 📦 Enviando preferencia a Mercado Pago...")
        print(f"[PAGAR] ✅ Success URL: {preference_data['back_urls']['success']}")
        print(f"[PAGAR] ✅ Failure URL: {preference_data['back_urls']['failure']}")
        print(f"[PAGAR] ✅ Pending URL: {preference_data['back_urls']['pending']}")
        
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {}) or {}
        
        if not preference.get("id"):
            print(f"[PAGAR] ❌ Error al generar preferencia: {preference_response}")
            return jsonify({'error': 'No se pudo generar la preferencia de pago'}), 500
        
        print(f"[PAGAR] ✅ Preferencia creada: ID={preference.get('id')}")
        print(f"[PAGAR] ✅ Punto de inicio: {preference.get('init_point')[:100]}...")
        
        # 8. Guardar orden en Firestore
        orden_doc = {
            "email_vendedor": email_vendedor,
            "numero_vendedor": numero_vendedor,
            "cliente_nombre": cliente_nombre,
            "cliente_email": cliente_email,
            "cliente_telefono": cliente_telefono,
            "carrito": carrito,
            "items_mp": items_para_mp,
            "items": items_para_mp,
            "total": total_final,
            "estado": "pendiente",
            "preference_id": preference.get("id"),
            "external_reference": external_ref,
            "comprobante_enviado": False,
            "fecha_creacion": firestore.SERVER_TIMESTAMP,
            "actualizado": firestore.SERVER_TIMESTAMP,
            "metadata": {
                "cliente": cliente_nombre,
                "email_cliente": cliente_email,
                "telefono_cliente": cliente_telefono,
                "total_items": len(items_para_mp),
                "url_retorno": url_retorno,
                "ids_items": [item.get('id') for item in items_para_mp]  # 🔥 Nuevo: lista de IDs para debug
            }
        }
        
        db.collection("ordenes").document(external_ref).set(orden_doc)
        print(f"[PAGAR] ✅ Orden guardada en Firestore: {external_ref}")
        print(f"[PAGAR] 🔍 IDs en items_mp: {[item.get('id') for item in items_para_mp]}")
        
        # 9. Guardar en la subcolección de pedidos del VENDEDOR
        pedido_data = {
            "cliente_nombre": cliente_nombre,
            "cliente_email": cliente_email,
            "cliente_telefono": cliente_telefono,
            "carrito": carrito,
            "items_mp": items_para_mp,
            "total": total_final,
            "estado": "pendiente",
            "preference_id": preference.get("id"),
            "external_reference": external_ref,
            "fecha_creacion": firestore.SERVER_TIMESTAMP,
            "comprobante_enviado": False,
            "url_retorno": url_retorno
        }
        
        db.collection("usuarios").document(email_vendedor)\
          .collection("pedidos").document(external_ref).set(pedido_data)
        print(f"[PAGAR] ✅ Orden guardada en subcolección del vendedor")
        
        # 10. Devolver respuesta
        response_data = {
            "preference_id": preference.get("id"),
            "init_point": preference.get("init_point"),
            "external_reference": external_ref,
            "orden_id": external_ref,
            "total": total_final,
            "message": "Orden creada exitosamente",
            "detalle": f"Procesados {len(items_para_mp)} productos",
            "url_retorno": url_retorno,
            "debug": {
                "ids_items": [item.get('id') for item in items_para_mp],
                "tiene_carrito": len(carrito) > 0,
                "tiene_items_mp": len(items_para_mp) > 0
            }
        }
        
        print(f"[PAGAR] 📤 Enviando respuesta: {json.dumps(response_data, indent=2)}")
        return jsonify(response_data)

    except Exception as e:
        print(f"[PAGAR] ❌ Error interno: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Error interno al generar el pago',
            'message': str(e),
            'detalle': 'Revisa los logs del servidor'
        }), 500
        
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
            # 🔑 generar token único
            token = secrets.token_urlsafe(32)

            # 👉 devolver email y token al frontend
            return jsonify({
                'status': 'ok',
                'token': token,
                'email': usuario
            })
        else:
            return jsonify({'status': 'error', 'message': 'Clave incorrecta'}), 403

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/logout-admin')
def logout_admin():
    session.pop('modo_admin', None)
    return redirect('/preview')

@app.route("/guardar-producto", methods=["POST"])
def guardar_producto():
    try:
        print("\n[GUARDAR_PRODUCTO] 🚀 Nueva petición recibida")

        # 1) Parsear body
        data = request.get_json(force=True) or {}
        print(f"[GUARDAR_PRODUCTO] Body recibido: {data}")

        email = data.get("email")
        producto = data.get("producto")

        # 2) Validaciones mínimas
        if not email:
            print("[GUARDAR_PRODUCTO] ❌ Falta email en body")
            return jsonify({"status": "error", "error": "Falta email"}), 403

        if not producto:
            print("[GUARDAR_PRODUCTO] ❌ Falta producto en body")
            return jsonify({"status": "error", "error": "Producto inválido"}), 400

        # NUEVO: Debug del stock
        print(f"[GUARDAR_PRODUCTO] Stock recibido en producto: {producto.get('stock')}")
        print(f"[GUARDAR_PRODUCTO] Datos validados → email={email}")

        # 3) Guardar usando función robusta
        print("[GUARDAR_PRODUCTO] → Llamando a subir_a_firestore()")
        resultado = subir_a_firestore(producto, email)

        # 4) Respuesta normalizada
        response_data = {
            "status": "ok",
            "email": email,
            "producto_id": producto.get("id_base"),
            "resultado": resultado
        }
        print(f"[GUARDAR_PRODUCTO] 📤 Enviando respuesta: {json.dumps(response_data, indent=2)}")
        return jsonify(response_data)

    except Exception as e:   # 👈 alineado con el try
        print(f"[GUARDAR_PRODUCTO] ❌ Error interno: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'error': str(e),
            'detalle': 'Revisa los logs del servidor'
        }), 500

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
    
@app.route("/eliminar-producto", methods=["POST"])
def eliminar_producto():
    try:
        data = request.get_json(force=True) or {}
        email = data.get("email")
        id_base = data.get("id_base")

        if not email or not id_base:
            return jsonify({"status": "error", "error": "Faltan datos"}), 400

        productos_ref = db.collection("usuarios").document(email).collection("productos")
        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            print(f"[ELIMINAR_PRODUCTO] ⚠️ No encontrado → Usuario={email}, id_base={id_base}")
            return jsonify({"status": "not_found", "id_base": id_base}), 404

        doc = query[0]
        doc.reference.delete()
        print(f"[ELIMINAR_PRODUCTO] ✅ Eliminado en Firestore → Usuario={email}, id_base={id_base}")
        return jsonify({"status": "ok", "id_base": id_base})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("[ELIMINAR_PRODUCTO] 💥 Error inesperado:", e)
        return jsonify({"status": "error", "error": str(e), "trace": tb}), 500

@app.route('/actualizar-precio', methods=['POST'])
def actualizar_precio():
    data = request.get_json() or {}
    id_base = data.get("id")
    nuevo_precio_raw = data.get("nuevoPrecio", 0)
    email = data.get("email")   # 👈 igual que en talles

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
        print(f"[ACTUALIZAR-PRECIO] ✅ Usuario={email}, id_base={id_base}, precio={nuevo_precio}")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[ACTUALIZAR-PRECIO] ❌ Error: {e}")
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

        email = request.form.get('email')
        if email:
            session['email'] = email.strip()
            print(f"✅ Email guardado en sesión: {session['email']}")
        else:
            print("⚠️ No se recibió email en step1")
            
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
        stocks = request.form.getlist('stock')  # 👈 NUEVO: campo stock
        imagenes_elegidas = request.form.getlist('imagen_elegida')

        print(f"📊 [Step3] Datos recibidos: nombres={len(nombres)}, precios={len(precios)}, stocks={len(stocks)}, imagenes_elegidas={len(imagenes_elegidas)}")

        repo_name = session.get('repo_nombre') or "AppWeb"
        print(f"📦 [Step3] Repo destino: {repo_name}")

        for i in range(len(nombres)):
            nombre = nombres[i].strip()
            precio = precios[i].strip()
            grupo = grupos[i].strip() or 'Sin grupo'
            subgrupo = subgrupos[i].strip() or 'Sin subgrupo'
            orden = ordenes[i].strip() or str(i + 1)
            
            # 👈 NUEVO: procesar stock
            stock_raw = stocks[i] if i < len(stocks) else "0"
            print(f"  [Step3] Stock raw recibido para producto {i+1}: '{stock_raw}'")
            
            # Procesar stock para convertirlo a int
            stock_final = 0
            if stock_raw and str(stock_raw).strip():
                try:
                    stock_final = int(str(stock_raw).strip())
                    if stock_final < 0:
                        stock_final = 0
                        print(f"  [Step3] ⚠️ Stock negativo ajustado a 0")
                except (ValueError, TypeError) as e:
                    print(f"  [Step3] ⚠️ Error parseando stock '{stock_raw}': {e}, usando default 0")
                    stock_final = 0
            else:
                print(f"  [Step3] ℹ️ Stock vacío o no proporcionado, usando default 0")
            
            print(f"➡️ [Step3] Procesando producto {i+1}: nombre={nombre}, precio={precio}, stock={stock_final}, grupo={grupo}, subgrupo={subgrupo}, orden={orden}")

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
                'stock': stock_final,  # 👈 NUEVO: incluir stock en el bloque
                'imagen_url': imagen_para_guardar,
                'grupo': grupo,
                'subgrupo': subgrupo,
                'orden': orden,
                'talles': talle_lista
            })
            print(f"✅ [Step3] Producto agregado: {nombre} con imagen {imagen_para_guardar}, stock={stock_final}")

        session['bloques'] = bloques
        print(f"📊 [Step3] Total bloques construidos: {len(bloques)}")
        exitos = 0

        def subir_con_resultado(producto):
            try:
                print(f"🔥 [Step3] Subiendo producto a Firestore: {producto.get('nombre')}, stock={producto.get('stock')}")
                resultado = subir_a_firestore(producto, email)
                print(f"🔥 [Step3] Resultado subir_a_firestore para '{producto.get('nombre')}' -> {resultado}")
                
                # Verificar si fue exitoso
                if isinstance(resultado, dict):
                    return resultado.get("status") == "ok" or resultado.get("ok") == True
                else:
                    return bool(resultado)
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
            print(f"📊 [Step3] Lote completado: {sum(1 for r in resultados if r)} exitos")
        
        print(f"📊 [Step3] Total exitos en Firestore: {exitos} de {len(bloques)} intentados")

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
            print(f"➡️ [Step3] {exitos} productos guardados exitosamente, redirigiendo a /preview")
            # Limpiar imágenes de sesión para liberar memoria
            session.pop('imagenes_step0', None)
            return redirect(f"/preview?email={email}&step3_completado=true&guardados={exitos}")
        else:
            print("⚠️ [Step3] Ningún producto subido exitosamente, renderizando step3.html")
            return render_template(
                'step3.html',
                tipo_web=tipo,
                imagenes_step0=imagenes_disponibles,
                email=email,
                productos=bloques  # 👈 Pasar productos para rellenar formulario
            )

    print("ℹ️ [Step3] GET request, renderizando step3.html")
    return render_template(
        'step3.html',
        tipo_web=tipo,
        imagenes_step0=imagenes_disponibles,
        email=email
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

@app.route('/conectar_mp', methods=["GET"])
def conectar_mp():
    print("\n[MP-CONNECT] 🚀 Nueva petición de conexión a Mercado Pago")

    email = request.args.get("email")
    url_retorno = request.args.get("url_retorno")
    print(f"[MP-CONNECT] Email recibido: {email}, url_retorno={url_retorno}")

    if not email:
        print("[MP-CONNECT] ❌ Falta email en la query")
        return "Error: falta email", 403

    # 🔑 Validar que el usuario exista en Firestore
    try:
        doc_ref = db.collection("usuarios").document(email).collection("config").document("mercado_pago")
        snap = doc_ref.get()
        if not snap.exists:
            print(f"[MP-CONNECT] ⚠️ No existe config de Mercado Pago para {email} (se creará en callback)")
        else:
            print(f"[MP-CONNECT] ✅ Config de Mercado Pago encontrada para {email}")
    except Exception as e:
        print(f"[MP-CONNECT] 💥 Error validando usuario en Firestore: {e}")
        return "Error interno", 500

    client_id = os.getenv("MP_CLIENT_ID")
    if not client_id:
        print("[MP-CONNECT] ❌ Falta configurar MP_CLIENT_ID en entorno")
        return "❌ Falta configurar MP_CLIENT_ID en entorno", 500

    redirect_uri = url_for("callback_mp", _external=True)
    print(f"[MP-CONNECT] Redirect URI generada: {redirect_uri}")

    # 🔴 PROBLEMA: NO usar quote() aquí, solo JSON
    # Mercado Pago espera un string simple, no un JSON codificado
    # Si queremos pasar email y url_retorno, mejor usar un separador simple
    state_data = f"{email}|{url_retorno or ''}"
    
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "read write offline_access",
        "state": state_data  # 👈 String simple, no JSON codificado
    })
    auth_url = f"https://auth.mercadopago.com/authorization?{query}"

    print(f"[MP-CONNECT] 🔗 URL de autorización construida: {auth_url}")
    print(f"[MP-CONNECT] 🔗 State enviado: {state_data}")
    return redirect(auth_url)

@app.route('/callback_mp')
def callback_mp():
    print("\n[MP-CALLBACK] 🚀 Callback de Mercado Pago recibido")

    # 🔑 Validar credenciales recibidas en query
    code = request.args.get('code')
    state_data = request.args.get('state')  # Ahora es un string simple

    print(f"[MP-CALLBACK] Parámetros recibidos → code={code}, state={state_data}")

    if not state_data:
        print("[MP-CALLBACK] ❌ Falta parámetro state")
        return "Error: falta parámetro state", 403
    if not code:
        print("[MP-CALLBACK] ❌ No se recibió código de autorización")
        return "❌ No se recibió código de autorización", 400

    # Parsear el state simple: "email|url_retorno"
    parts = state_data.split('|')
    email = parts[0] if len(parts) > 0 else ""
    url_retorno = parts[1] if len(parts) > 1 else None

    # Si url_retorno está vacío, usar None
    if url_retorno == "":
        url_retorno = None

    print(f"[MP-CALLBACK] Email obtenido: {email}")
    print(f"[MP-CALLBACK] URL retorno obtenida: {url_retorno}")

    if not email:
        print("[MP-CALLBACK] ❌ No se pudo obtener email del state")
        return "❌ Error: email no encontrado en state", 400

    client_id = os.getenv("MP_CLIENT_ID")
    client_secret = os.getenv("MP_CLIENT_SECRET")
    redirect_uri = url_for('callback_mp', _external=True)

    print(f"[MP-CALLBACK] Procesando para email: {email}")
    print(f"[MP-CALLBACK] URL de retorno: {url_retorno}")

    token_url = "https://api.mercadopago.com/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }

    try:
        print(f"[MP-CALLBACK] 📡 Enviando payload a {token_url}")
        response = requests.post(token_url, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"[MP-CALLBACK] ✅ Token obtenido exitosamente")

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token:
            print("[MP-CALLBACK] ❌ No se obtuvo access_token")
            return "❌ Error al obtener token de Mercado Pago", 400

        # ✅ Obtener la public_key
        public_key = data.get("public_key")
        if not public_key:
            try:
                cred_resp = requests.get(
                    "https://api.mercadopago.com/v1/account/credentials",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10
                )
                if cred_resp.status_code == 200:
                    cred_data = cred_resp.json() or {}
                    public_key = cred_data.get("public_key") or cred_data.get("web", {}).get("public_key")
                if not public_key:
                    user_resp = requests.get(
                        "https://api.mercadopago.com/users/me",
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=10
                    )
                    if user_resp.status_code == 200:
                        user_data = user_resp.json() or {}
                        public_key = user_data.get("public_key")
            except Exception as e:
                print("[MP-CALLBACK] 💥 Error al obtener public_key:", e)

        if public_key and isinstance(public_key, str):
            public_key = public_key.strip()
            print(f"[MP-CALLBACK] ✅ Public key obtenida: {public_key[:30]}...")

        # ✅ Guardar credenciales en Firestore
        doc_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": datetime.now().isoformat(),
            "live_mode": data.get("live_mode"),
            "scope": data.get("scope"),
            "user_id": data.get("user_id"),
        }
        if public_key:
            doc_data["public_key"] = public_key

        db.collection("usuarios").document(email).collection("config").document("mercado_pago").set(
            doc_data, merge=True
        )
        print(f"[MP-CALLBACK] ✅ Credenciales guardadas en Firestore para {email}")

        # 🔄 Redirigir al dominio del usuario si vino en state
        if url_retorno:
            # Asegurar que la URL tenga el parámetro de configuración exitosa
            destino = url_retorno.rstrip("/")
            
            # Construir URL con parámetros
            if "?" in destino:
                redirect_url = f"{destino}&mp_configurado=true&email={email}"
            else:
                redirect_url = f"{destino}?mp_configurado=true&email={email}"
            
            print(f"[MP-CALLBACK] ➡️ Redirigiendo a la página del usuario: {redirect_url}")
            return redirect(redirect_url)
        else:
            # fallback: preview interno
            preview_url = f"https://mpagina.onrender.com/preview?email={email}&mp_configurado=true"
            print(f"[MP-CALLBACK] ➡️ Redirigiendo a preview interno: {preview_url}")
            return redirect(preview_url)

    except Exception as e:
        print("[MP-CALLBACK] 💥 Error general en callback_mp:", e)
        import traceback
        traceback.print_exc()
        
        # Intentar redirigir de todos modos con mensaje de error
        if url_retorno:
            error_url = f"{url_retorno}?mp_error=1&email={email}"
            return redirect(error_url)
        else:
            return "Error al conectar con Mercado Pago", 500
        
@app.route("/api/mp_public_key")
def api_mp_public_key():
    email = request.args.get("email")
    if not email:
        return jsonify({"error": "Falta email"}), 400

    public_key = (get_mp_public_key(email) or "").strip()
    if not public_key:
        return jsonify({"error": "No hay public_key configurada"}), 404

    return jsonify({"public_key": public_key})
        
@app.route('/preview', methods=["GET"])
def preview():
    print("\n🚀 [Preview] Entrando a /preview")

    # 📧 Obtener email desde query o sesión
    email = request.args.get('email') or session.get("email")
    orden_id = request.args.get("orden_id")
    print(f"[Preview] Email recibido: {email}, orden_id={orden_id}")
    if not email:
        print("[Preview] ❌ Falta email en query o sesión")
        return "Error: falta email", 400

    # 🎨 Config visual desde Firestore
    try:
        config_doc = db.collection("usuarios").document(email).collection("config").document("general").get()
        config_data = config_doc.to_dict() if config_doc.exists else {}
        print(f"[Preview] Config visual obtenida: {config_data}")
    except Exception as e:
        print(f"[Preview] 💥 Error leyendo config visual: {e}")
        config_data = {}

    estilo_visual = config_data.get("estilo_visual", "claro_moderno")
    print(f"[Preview] Estilo visual: {estilo_visual}")

    # 📦 Productos
    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        for doc in productos_ref.stream():
            productos.append(doc.to_dict())
        productos = sorted(productos, key=lambda p: p.get('orden', 0))
        print(f"[Preview] Productos cargados: {len(productos)}")
    except Exception as e:
        print(f"[Preview] 💥 Error leyendo productos: {e}")

    # 🧱 Agrupar productos por grupo/subgrupo
    grupos_dict = {}
    for p in productos:
        grupo = (p.get('grupo') or 'General').strip().title()
        subgrupo = (p.get('subgrupo') or 'Sin Subgrupo').strip().title()
        grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(p)
    print(f"[Preview] Grupos generados: {list(grupos_dict.keys())}")

    # 💳 Credenciales de Mercado Pago
    mercado_pago_token = get_mp_token(email)
    public_key = (get_mp_public_key(email) or "").strip()
    print(f"[Preview] Mercado Pago token presente: {bool(mercado_pago_token)}")
    print(f"[Preview] Public key obtenida: '{public_key}'")

    # ⚙️ Configuración final que se pasa al template
    config = {
        **config_data,
        'email': email,
        'orden_id': orden_id,              # 👈 añadido para trazabilidad del formulario cliente
        'estilo_visual': estilo_visual,
        'mercado_pago': bool(mercado_pago_token),
        'public_key': public_key,
        'productos': productos,
        'usarFirestore': True
    }
    print(f"[Preview] Config final enviada al template: {list(config.keys())}")

    # ✅ Renderizar template
    return render_template(
        'preview.html',
        config=config,
        grupos=grupos_dict,
        firebase_config=firebase_config
    )

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
