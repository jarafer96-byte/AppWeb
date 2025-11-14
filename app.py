from flask import Flask, render_template, redirect, session, send_file, url_for, jsonify, current_app, request, flash
import requests
import os
import uuid
import re
import time
import json
import gc
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
        print("❌ Producto incompleto, faltan campos obligatorios")
        return False

    grupo_original = producto["grupo"].strip()
    subgrupo_original = producto.get("subgrupo", "general").strip()
    nombre_original = producto["nombre"].strip()

    grupo_id = grupo_original.replace(" ", "_").lower()
    nombre_id = nombre_original.replace(" ", "_").lower()
    fecha = time.strftime("%Y%m%d")

    # ✅ Sufijo único para evitar colisiones sin perder trazabilidad
    sufijo = uuid.uuid4().hex[:6]
    custom_id = f"{nombre_id}_{fecha}_{grupo_id}_{sufijo}"

    try:
        precio = int(producto["precio"].replace("$", "").replace(".", "").strip())
        orden = int(producto.get("orden", 999))
    except ValueError:
        print(f"❌ Precio u orden inválido en producto: {producto['nombre']}")
        return False

    talles = producto.get("talles") or []
    if isinstance(talles, str):
        talles = [t.strip() for t in talles.split(',') if t.strip()]

    try:
        producto["id_base"] = custom_id  # ✅ Trazabilidad para frontend y edición

        # 🔍 Logs de depuración
        print(f"🖼️ Imagen Backblaze a guardar: {producto.get('imagen_backblaze')}")
        print(f"🖼️ Imagen GitHub a guardar: {producto.get('imagen_github')}")

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

        print(f"✅ Producto subido correctamente: {nombre_original} | ID base: {custom_id}")
        print("📄 Documento Firestore:")

        # ✅ Evitar error de Sentinel en el log
        log_doc = {k: v for k, v in doc.items() if k != "timestamp"}
        print(json.dumps(log_doc, indent=2))

        return True
    except Exception as e:
        print(f"❌ Error al subir {nombre_original}:", e)
        return False

def subir_archivo(repo, contenido_bytes, ruta_remota, token, branch="main"):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo}/contents/{ruta_remota}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Primero obtenemos el SHA si el archivo ya existe
    try:
        r_get = requests.get(url, headers=headers, timeout=10)
        sha = None
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")
    except Exception as e:
        print(f"⚠️ Error al verificar existencia de {ruta_remota}: {e}")
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
            print(f"✅ Subido/actualizado: {ruta_remota}")
            return {
                "ok": True,
                "url": r.json().get("content", {}).get("html_url"),
                "status": r.status_code
            }
        else:
            print(f"❌ Error al subir {ruta_remota}: {r.status_code} → {r.text}")
            return {"ok": False, "status": r.status_code, "error": r.text}
    except Exception as e:
        print(f"❌ Error inesperado al subir {ruta_remota}: {e}")
        return {"ok": False, "error": str(e)}

def subir_iconos_png(repo, token):
    carpeta = os.path.join("static", "img")
    for nombre_archivo in os.listdir(carpeta):
        if nombre_archivo.lower().endswith(".png"):
            ruta_local = os.path.join(carpeta, nombre_archivo)
            ruta_remota = f"static/img/{nombre_archivo}"
            with open(ruta_local, "rb") as f:
                contenido = f.read()
            exito = subir_archivo(repo, contenido, ruta_remota, token)
            if exito:
                print(f"✅ PNG subido: {ruta_remota}")
            else:
                print(f"❌ Falló subida de: {ruta_remota}")

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
        print("❌ Token no cargado desde entorno")
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
            print(f"✅ Repositorio creado: {repo_url}")
            return {"url": repo_url}
        else:
            print(f"⚠️ Error {response.status_code}: {response.text}")
            return {"error": response.text}
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de red: {e}")
        return {"error": str(e)}

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

def redimensionar_y_subir(imagen, email):
    try:
        print(f"📥 Recibida imagen: {imagen.filename}")
        pil = Image.open(imagen).convert("RGBA")

        # Tamaño fijo
        target_size = (300, 200)

        # Calcular proporciones
        img_ratio = pil.width / pil.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)

        # Redimensionar manteniendo proporción
        pil = pil.resize((new_width, new_height), Image.LANCZOS)

        # Crear lienzo transparente fijo
        fondo = Image.new("RGBA", target_size, (0, 0, 0, 0))
        offset = ((target_size[0] - new_width) // 2, (target_size[1] - new_height) // 2)
        fondo.paste(pil, offset, pil)

        buffer = BytesIO()
        fondo.save(buffer, format="WEBP", quality=80)
        buffer.seek(0)

        nombre = f"mini_{uuid.uuid4().hex}.webp"
        ruta_s3 = f"usuarios/{email}/{nombre}"

        # ✅ Guardar también en /tmp para GitHub
        ruta_tmp = os.path.join("/tmp", nombre)
        with open(ruta_tmp, "wb") as f:
            f.write(buffer.getvalue())
        print(f"💾 Copia guardada en tmp: {ruta_tmp}")

        # Subir a Backblaze
        s3.upload_fileobj(buffer, BUCKET, ruta_s3, ExtraArgs={'ContentType': 'image/webp'})
        url_final = f"https://{BUCKET}.s3.us-west-004.backblazeb2.com/{ruta_s3}"
        print(f"✅ Subida exitosa a Backblaze: {url_final}")
        return url_final
    except Exception as e:
        print(f"❌ Error al subir {imagen.filename}: {e}")
        return None

def normalizar_url(url: str) -> str:
    """
    Convierte cualquier URL completa en una ruta relativa usable en el template.
    Ejemplo:
    https://f005.backblazeb2.com/file/imagenes-appweb/usuarios/.../mini_xxx.webp
    → usuarios/.../mini_xxx.webp
    """
    if "/file/imagenes-appweb/" in url:
        return url.split("/file/imagenes-appweb/")[1]
    elif "s3.us-west-004.backblazeb2.com" in url or "s3.us-east-005.backblazeb2.com" in url:
        # extraer después del bucket
        if "/usuarios/" in url:
            return "usuarios/" + url.split("/usuarios/")[1]
    return url  # fallback si no coincide

@app.route('/step0', methods=['GET', 'POST'])
def step0():
    if request.method == 'POST':
        email = session.get('email', 'anonimo')
        imagenes = request.files.getlist('imagenes')
        print(f"📦 Tanda recibida: {len(imagenes)} archivos")

        if not imagenes:
            print("⚠️ No se recibieron imágenes")
            return "No se recibieron imágenes", 400

        if 'imagenes_step0' not in session:
            session['imagenes_step0'] = []

        if len(session['imagenes_step0']) + len(imagenes) > 120:
            print("⚠️ Límite de 60 imágenes alcanzado")
            return "Límite de imágenes alcanzado", 400

        # ✅ Función auxiliar para dividir en lotes
        def chunks(lista, n):
            for i in range(0, len(lista), n):
                yield lista[i:i+n]

        urls = []
        # Procesar en tandas de 10 imágenes, con 3 workers simultáneos por tanda
        for lote in chunks([img for img in imagenes if img and img.filename], 40):
            print(f"🚚 Procesando lote de {len(lote)} imágenes")
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(redimensionar_y_subir, img, email) for img in lote]
                for f in futures:
                    url = f.result()
                    if url:
                        urls.append(normalizar_url(url))  # ✅ siempre normalizamos

        session['imagenes_step0'].extend(urls)
        print(f"🧠 Total acumulado en sesión: {len(session['imagenes_step0'])}")
        return redirect('/estilo')

    return render_template('step0.html')

def get_token_vendedor_por_external(external_reference: str) -> str:
    """
    Recupera el access_token del vendedor asociado a un external_reference.
    """
    try:
        # Buscar la orden en tu base de datos
        orden = db.collection("ordenes").document(external_reference).get()
        if orden.exists:
            data = orden.to_dict()
            vendedor_id = data.get("vendedor_id")

            # Buscar el token del vendedor en la colección de vendedores
            vendedor = db.collection("vendedores").document(vendedor_id).get()
            if vendedor.exists:
                return vendedor.to_dict().get("access_token")

    except Exception as e:
        log_event("get_token_vendedor_error", str(e))

    return None

def get_token_vendedor_por_external(external_reference: str) -> str:
    """
    Recupera el access_token del vendedor asociado a un external_reference.
    """
    try:
        # Buscar la orden en tu base de datos
        orden = db.collection("ordenes").document(external_reference).get()
        if orden.exists:
            data = orden.to_dict()
            vendedor_id = data.get("vendedor_id")

            # Buscar el token del vendedor en la colección de vendedores
            vendedor = db.collection("vendedores").document(vendedor_id).get()
            if vendedor.exists:
                return vendedor.to_dict().get("access_token")

    except Exception as e:
        log_event("get_token_vendedor_error", str(e))

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
    log_event("mp_webhook", event)  # auditoría

    topic = event.get("type") or event.get("action")
    payment_id = None
    if topic == "payment" and event.get("data", {}).get("id"):
        payment_id = event["data"]["id"]

    if payment_id:
        try:
            # Primero consultamos el detalle del pago con un token "plataforma"
            # para obtener el external_reference y saber a qué vendedor pertenece
            detail = requests.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {get_platform_token()}"}
            ).json()

            ext_ref = detail.get("external_reference")
            status = detail.get("status")
            payer = detail.get("payer", {})
            seller_user_id = detail.get("sponsor_id") or detail.get("collector_id")

            # 🔑 Buscar el access_token del vendedor según el external_reference
            seller_token = get_token_vendedor_por_external(ext_ref)
            if seller_token:
                # Reconsultar el detalle con el token del vendedor para trazabilidad completa
                detail = requests.get(
                    f"https://api.mercadopago.com/v1/payments/{payment_id}",
                    headers={"Authorization": f"Bearer {seller_token}"}
                ).json()
                status = detail.get("status") or status
                seller_user_id = detail.get("collector_id") or seller_user_id

            # Actualizar tu orden interna con toda la info relevante
            actualizar_orden_por_external_reference(
                ext_ref,
                {
                    "payment_id": payment_id,
                    "status": status,
                    "seller_user_id": seller_user_id,
                    "payer": payer,
                    "transaction_amount": detail.get("transaction_amount"),
                    "payment_method_id": detail.get("payment_method_id"),
                    "date_approved": detail.get("date_approved"),
                    "raw": detail
                }
            )

        except Exception as e:
            log_event("mp_webhook_error", str(e))

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

    print("📥 Datos recibidos:", data)

    if not usuario or not clave:
        print("❌ Faltan datos: usuario o clave vacíos")
        return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

    try:
        # 🔄 Limpiar sesión anterior y activar nueva
        session.clear()
        session['email'] = usuario
        session['modo_admin'] = True
        print("🧠 Sesión iniciada para:", session['email'])

        # 🔐 Guardar en Firestore
        doc_ref = db.collection("usuarios").document(usuario)
        doc_ref.set({
            "clave_admin": clave
        })
        print(f"✅ Admin creado correctamente: {usuario}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("❌ Error al guardar en Firestore:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/login-admin', methods=['POST'])
def login_admin():
    session.clear()

    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario')
    clave_ingresada = data.get('clave')

    print("🔐 Intentando login:", usuario)
    print("🔐 Clave ingresada:", clave_ingresada)

    if not usuario or not clave_ingresada:
        print("❌ Faltan datos para login")
        return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", usuario):
        print("❌ Usuario no tiene formato de email:", usuario)
        return jsonify({'status': 'error', 'message': 'El usuario debe tener formato de email'}), 400

    try:
        doc_ref = db.collection("usuarios").document(usuario)
        doc = doc_ref.get()

        if not doc.exists:
            print("❌ Usuario no encontrado en Firestore")
            return jsonify({'status': 'error', 'message': 'Usuario no registrado'}), 404

        clave_guardada = doc.to_dict().get("clave_admin")
        print("🔐 Clave guardada en Firestore:", clave_guardada)

        if clave_guardada == clave_ingresada:
            session.permanent = True
            session['modo_admin'] = True
            session['email'] = usuario  # ✅ Ahora sí, usuario ya está definido
            print("✅ Login exitoso → modo_admin activado")
            return jsonify({'status': 'ok'})
        else:
            print("❌ Clave incorrecta")
            return jsonify({'status': 'error', 'message': 'Clave incorrecta'}), 403

    except Exception as e:
        print("❌ Error al validar login:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/logout-admin')
def logout_admin():
    session.pop('modo_admin', None)
    print("🔓 Sesión admin cerrada")
    return redirect('/preview')

@app.route('/guardar-producto', methods=['POST'])
def guardar_producto():
    usuario = session.get('email')
    if not usuario:
        print("❌ No hay usuario en sesión")
        return jsonify({'status': 'error', 'message': 'No estás logueado'}), 403

    data = request.get_json(silent=True) or {}
    producto = data.get('producto')

    if not producto:
        print("⚠️ No se recibió producto válido")
        return jsonify({'status': 'error', 'message': 'Producto inválido'}), 400

    try:
        ruta = f"usuarios/{usuario}/productos"
        db.collection(ruta).add(producto)
        print(f"✅ Producto guardado para {usuario}: {producto.get('nombre', 'sin nombre')}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("❌ Error al guardar producto:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/ver-productos')
def ver_productos():
    usuario = session.get('email')
    if not usuario:
        print("❌ No hay usuario en sesión")
        return jsonify([])

    try:
        ruta = f"usuarios/{usuario}/productos"
        docs = db.collection(ruta).get()
        productos = [doc.to_dict() for doc in docs]
        print(f"📦 Productos cargados para {usuario}: {len(productos)}")
        return jsonify(productos)
    except Exception as e:
        print("❌ Error al cargar productos:", e)
        return jsonify([])

@app.route("/crear-repo", methods=["POST"])
def crear_repo():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "❌ Token no cargado desde entorno", 500

    email = request.json.get("email", f"repo-{uuid.uuid4().hex[:6]}")
    session['email'] = email
    nombre_repo = generar_nombre_repo(email)
    session['repo_nombre'] = nombre_repo  # ✅ ESTA LÍNEA ES CLAVE

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

    print("🔧 Intentando actualizar precio:", id_base, "→", nuevo_precio_raw)

    if not email or not id_base:
        print("❌ Datos incompletos")
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        nuevo_precio = int(nuevo_precio_raw)
    except ValueError:
        print("❌ Precio inválido:", nuevo_precio_raw)
        return jsonify({"error": "Precio inválido"}), 400

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            print("❌ Producto no encontrado:", id_base)
            return jsonify({"error": "Producto no encontrado"}), 404

        doc = query[0]
        doc.reference.update({"precio": nuevo_precio})
        print("💰 Precio actualizado:", id_base, "→", nuevo_precio)
        return jsonify({"status": "ok"})
    except Exception as e:
        print("❌ Error al actualizar precio:", e)
        import traceback
        traceback.print_exc()
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
        print("👟 Talles actualizados:", id_base)
        return jsonify({"status": "ok"})
    except Exception as e:
        print("❌ Error al actualizar talles:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/actualizar-firestore', methods=['POST'])
def actualizar_firestore():
    data = request.get_json(silent=True) or {}
    id_base = data.get('id')
    campos = {k: v for k, v in data.items() if k != 'id'}
    email = session.get("email")

    print("📥 Datos recibidos en /actualizar-firestore:", data)
    print("🧠 Email de sesión:", email)

    if not email or not id_base or not campos:
        print("❌ Datos incompletos:", {"email": email, "id_base": id_base, "campos": campos})
        return jsonify({'status': 'error', 'message': 'Datos incompletos'}), 400

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")

        print("🔎 Buscando documento con id_base:", id_base)
        print("📂 Documentos disponibles para usuario:", email)
        for doc in productos_ref.stream():
            doc_data = doc.to_dict()
            print("📄 Documento:", doc.id, "| id_base:", doc_data.get("id_base"), "| nombre:", doc_data.get("nombre"))

        query = productos_ref.where("id_base", "==", id_base).limit(1).get()

        if not query:
            print("❌ Producto no encontrado:", id_base)
            return jsonify({'status': 'error', 'message': 'Producto no encontrado'}), 404

        doc = query[0]
        doc.reference.update(campos)
        print(f"✅ Firestore actualizado para {id_base}: {campos}")
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("❌ Error al actualizar Firestore:", e)
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/', methods=['GET', 'POST'])
def step1():
    limpiar_imagenes_usuario()  # ✅ ahora preserva las imágenes

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
            print("✅ Credencial MP guardada:", session['mercado_pago'])
        else:
            session.pop('mercado_pago', None)
            print("🧹 Credencial MP eliminada por estar vacía o inválida")

        logo = request.files.get('logo')
        if logo:
            filename = secure_filename(logo.filename)
            if filename:
                logo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                session['logo'] = filename
        else:
            session['logo'] = None

        print("🧪 En step1, imágenes en sesión:", session.get('imagenes_step0'))  # ✅ validación
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

        return redirect('/contenido')

    imagenes = os.listdir('static/img/webp')
    return render_template('step2.html', config=session, imagenes=imagenes)
    

@app.route('/contenido', methods=['GET', 'POST'])
def step3():
    import gc

    tipo = session.get('tipo_web')
    email = session.get('email')
    imagenes_session = session.get('imagenes_step0') or []

    # 🔧 Normalizar las rutas a URLs completas para el carrusel
    imagenes_disponibles = [
        f"https://f005.backblazeb2.com/file/imagenes-appweb/{img}"
        for img in imagenes_session
    ]

    print(f"🧠 Imágenes disponibles en sesión (raw): {imagenes_session}")
    print(f"🧠 Imágenes normalizadas para render: {imagenes_disponibles}")

    if not email:
        print("❌ Sesión no válida")
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
        imagenes_elegidas = request.form.getlist('imagen_elegida')       # URL completa
        imagenes_basename = request.form.getlist('imagen_basename')      # basename real

        longitudes = [len(nombres), len(precios), len(descripciones), len(grupos),
                      len(subgrupos), len(ordenes), len(talles), len(imagenes_elegidas)]
        print("🧪 Longitudes:", longitudes)

        # ✅ Factorizar repo_name y token una sola vez
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

            if not imagen_url:
                print(f"⚠️ No se recibió imagen para fila {i+1}, se omite producto")
                continue
            else:
                print(f"🖼️ Imagen recibida para fila {i+1}: {imagen_url} | basename: {imagen_base}")

            talle_raw = talles[i].strip() if i < len(talles) else ''
            talle_lista = [t.strip() for t in talle_raw.split(',') if t.strip()]

            if not nombre or not precio or not grupo or not subgrupo:
                print(f"⚠️ Campos incompletos en fila {i+1}, se omite producto")
                continue

            # ✅ Backblaze: usar URL directa (ya viene completa del hidden)
            url_backblaze = imagen_url

            # ✅ GitHub: usar copia en /tmp con basename real
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
                    print(f"🌐 URL GitHub generada: {url_github}")

                    # ✅ liberar buffer y memoria
                    del contenido_bytes
                    gc.collect()
                except Exception as e:
                    print(f"❌ Error al subir a GitHub {imagen_base}: {e}")
                    url_github = ""
            else:
                print(f"⚠️ No existe en tmp o token ausente: {ruta_tmp}")
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
        fallos = 0

        def subir_con_resultado(producto):
            try:
                print(f"📤 Subiendo a Firestore: {producto}")
                return subir_a_firestore(producto, email)
            except Exception as e:
                print(f"❌ Error inesperado al subir {producto['nombre']}: {e}")
                return False

        bloques_por_lote = 10
        try:
            for inicio in range(0, len(bloques), bloques_por_lote):
                lote = bloques[inicio:inicio + bloques_por_lote]
                print(f"🚚 Subiendo lote {inicio//bloques_por_lote + 1} ({len(lote)} productos)")
                # ✅ Limitar a 3 workers simultáneos
                with ThreadPoolExecutor(max_workers=3) as executor:
                    resultados = list(executor.map(subir_con_resultado, lote))
                ok = sum(1 for r in resultados if r)
                fail = len(resultados) - ok
                exitos += ok
                fallos += fail
                print(f"📊 Resultado lote: ok={ok}, fail={fail}")
        except Exception as lote_error:
            print(f"🔥 Error crítico en lote de subida: {lote_error}")

        print(f"🧮 Subidos correctamente: {exitos} / Fallidos: {fallos}")

        # ✅ Subir index.html y los íconos PNG al repo
        if github_token and repo_name:
            try:
                # Renderizar index.html con los datos actuales
                html = render_template(
                    'preview.html',
                    config=session,
                    grupos={},  # puedes pasar grupos_dict si lo tenés armado aquí
                    modoAdmin=False,
                    modoAdminIntentado=False,
                    firebase_config=firebase_config
                )
                resultado_index = subir_archivo(
                    repo_name,
                    html.encode('utf-8'),
                    'index.html',
                    github_token
                )
                print("🧾 index.html subido:", resultado_index)
            except Exception as e:
                print("⚠️ No se pudo subir index.html:", e)

            try:
                subir_iconos_png(repo_name, github_token)
                print("🎨 Íconos PNG subidos correctamente")
            except Exception as e:
                print("⚠️ No se pudieron subir los íconos PNG:", e)

            # Subir logo
            logo = session.get('logo')
            if logo:
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        contenido = f.read()
                    subir_archivo(repo_name, contenido, f"static/img/{logo}", github_token)
                    print(f"🎯 Subido logo: {logo}")

            # Subir fondo visual
            estilo_visual = session.get('estilo_visual') or 'claro_moderno'
            fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{estilo_visual}.jpeg")
            if os.path.exists(fondo_path):
                with open(fondo_path, "rb") as f:
                    contenido = f.read()
                subir_archivo(repo_name, contenido, f"static/img/{estilo_visual}.jpeg", github_token)
                print(f"🌄 Subido fondo visual: {estilo_visual}.jpeg")

        try:
            if exitos > 0:
                return redirect('/preview')
            else:
                return render_template('step3.html', tipo_web=tipo, imagenes_step0=imagenes_disponibles)
        except Exception as e:
            import traceback
            print("🔥 Error al redirigir/renderizar preview:", e)
            traceback.print_exc()
            return render_template('step3.html', tipo_web=tipo, imagenes_step0=imagenes_disponibles)

    # GET
    print("🧪 tipo:", tipo)
    print("🧪 imagenes_step0 en render:", imagenes_disponibles)
    for idx, img in enumerate(imagenes_disponibles, start=1):
        print(f"🔎 Imagen {idx} enviada al template: {img}")

    return render_template('step3.html', tipo_web=tipo, imagenes_step0=imagenes_disponibles)
    
def get_mp_token(email: str):
    """Obtiene el token de Mercado Pago desde Firestore o Render."""
    try:
        if email:
            token_doc = db.collection("usuarios").document(email).collection("config").document("mercado_pago").get()
            if token_doc.exists:
                token_data = token_doc.to_dict()
                token = token_data.get("access_token")
                if token and isinstance(token, str):
                    return token.strip()
    except Exception as e:
        print("❌ Error al leer token de Firestore:", e)

    # Fallback: variable de entorno
    token = os.getenv("MERCADO_PAGO_TOKEN")
    if token and isinstance(token, str):
        return token.strip()

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

    # URL oficial de autorización de Mercado Pago
    auth_url = (
        f"https://auth.mercadopago.com/authorization?"
        f"client_id={client_id}&response_type=code&redirect_uri={redirect_uri}"
    )
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
        response = requests.post(token_url, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token:
            flash("❌ Error al obtener token de Mercado Pago")
            return redirect(url_for('preview', admin='true'))

        # ✅ Guardar en Firestore en subcolección config/mercado_pago
        email = session.get('email')
        if email:
            db.collection("usuarios").document(email).collection("config").document("mercado_pago").set({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "created_at": datetime.now().isoformat()
            })
            print(f"🔑 Token de Mercado Pago guardado en Firestore para: {email}")

        flash("✅ Mercado Pago conectado correctamente")
        return redirect(url_for('preview', admin='true'))

    except Exception as e:
        import traceback
        print("❌ Error en callback_mp:", e)
        traceback.print_exc()
        flash("Error al conectar con Mercado Pago")
        return redirect(url_for('preview', admin='true'))


@app.route('/pagar', methods=['POST'])
def pagar():
    try:
        data = request.get_json(silent=True) or {}
        carrito = data.get('carrito', [])

        # ✅ Recuperar SIEMPRE el token del vendedor (guardado tras OAuth)
        email = session.get('email')
        access_token = get_mp_token(email)  # tu helper debe devolver el token del vendedor

        if not access_token or not isinstance(access_token, str):
            print("❌ Token inválido o ausente:", access_token)
            return jsonify({'error': 'El vendedor no tiene credenciales de Mercado Pago configuradas'}), 400

        sdk = mercadopago.SDK(access_token.strip())

        # ✅ Construir items enriquecidos desde el carrito
        items = []
        if isinstance(carrito, list):
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
                    print("⚠️ Error procesando item del carrito:", e)

        # 🔑 Generar external_reference único
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

        if not preference.get("id"):
            print("⚠️ No se generó preference_id:", preference)
            return jsonify({'error': 'No se pudo generar la preferencia de pago'}), 500

        # ✅ Guardar orden en Firestore para trazabilidad del webhook
        db.collection("ordenes").document(external_ref).set({
            "external_reference": external_ref,
            "vendedor_id": email,
            "carrito": carrito,
            "estado": "pendiente",
            "created_at": firestore.SERVER_TIMESTAMP
        })

        print("✅ Preferencia creada correctamente:", preference["id"])
        return jsonify({
            "preference_id": preference["id"],
            "init_point": preference.get("init_point"),
            "external_reference": external_ref
        })

    except Exception as e:
        import traceback
        print("⚠️ Error en /pagar:", e)
        traceback.print_exc()
        return jsonify({'error': 'Error interno al generar el pago'}), 500


@app.route('/preview')
def preview():
    print("🚀 Entrando a /preview")
    modo_admin = session.get('modo_admin') is True and request.args.get('admin') == 'true'
    modo_admin_intentado = request.args.get('admin') == 'true'
    email = session.get('email')

    if not email:
        print("❌ Sesión no iniciada")
        return "Error: sesión no iniciada", 403

    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    # 🔄 Obtener productos desde Firestore
    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        productos_docs = productos_ref.stream()
        productos = [doc.to_dict() for doc in productos_docs]
        print(f"📦 Productos cargados desde Firestore: {len(productos)}")
    except Exception as e:
        print("❌ Error al obtener productos:", e)

    # 🧱 Agrupar por grupo y subgrupo
    grupos_dict = {}
    for producto in productos:
        grupo = producto.get('grupo', 'General').strip().title()
        subgrupo = producto.get('subgrupo', 'Sin subgrupo').strip().title()
        grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)

    # 🔑 Usar helper para verificar token de Mercado Pago
    mercado_pago_token = get_mp_token(email)

    # 🧠 Configuración visual
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
        'mercado_pago': bool(mercado_pago_token),  # ✅ ahora depende del helper
        'productos': productos,
        'bloques': [],
        'descargado': session.get('descargado', False),
        'usarFirestore': True
    }

    # ✅ Crear repo solo si el usuario lo pidió
    if session.get("crear_repo") and not session.get("repo_creado"):
        nombre_repo = generar_nombre_repo(email)
        print("📦 Intentando crear repo con:", nombre_repo)
        token = os.getenv("GITHUB_TOKEN")
        resultado = crear_repo_github(nombre_repo, token)
        print("📦 Resultado:", resultado)
        if "url" in resultado:
            session['repo_creado'] = resultado["url"]
            session['repo_nombre'] = nombre_repo
        else:
            print("⚠️ No se pudo crear el repositorio:", resultado.get("error"))
    else:
        print("ℹ️ Creación de repo omitida (no solicitada o ya existe).")

    # ✅ Subir archivos si el repo existe
    if session.get('repo_creado') and session.get('repo_nombre'):
        nombre_repo = session['repo_nombre']
        token = os.getenv("GITHUB_TOKEN")

        if not token:
            print("❌ GITHUB_TOKEN ausente, se omite subida de archivos.")
        else:
            # Subir imágenes de productos
            for producto in productos:
                imagen = producto.get("imagen")
                if imagen:
                    ruta_local = os.path.join(app.config['UPLOAD_FOLDER'], imagen)
                    if os.path.exists(ruta_local):
                        try:
                            with open(ruta_local, "rb") as f:
                                contenido = f.read()
                            subir_archivo(nombre_repo, contenido, f"static/img/{imagen}", token)
                            print(f"🖼️ Subida imagen: {imagen}")
                            del contenido
                            gc.collect()
                        except Exception as e:
                            print(f"❌ Error al subir imagen {imagen}: {e}")
                    else:
                        print(f"⚠️ Imagen no encontrada: {imagen}")

            # Subir logo
            logo = config.get("logo")
            if logo:
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                if os.path.exists(logo_path):
                    try:
                        with open(logo_path, "rb") as f:
                            contenido = f.read()
                        subir_archivo(nombre_repo, contenido, f"static/img/{logo}", token)
                        print(f"🎯 Subido logo: {logo}")
                        del contenido
                        gc.collect()
                    except Exception as e:
                        print(f"❌ Error al subir logo {logo}: {e}")
                else:
                    print(f"⚠️ Logo no encontrado: {logo}")

            # Subir fondo visual
            fondo = f"{estilo_visual}.jpeg"
            fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], fondo)
            if os.path.exists(fondo_path):
                try:
                    with open(fondo_path, "rb") as f:
                        contenido = f.read()
                    subir_archivo(nombre_repo, contenido, f"static/img/{fondo}", token)
                    print(f"🌄 Subido fondo visual: {fondo}")
                    del contenido
                    gc.collect()
                except Exception as e:
                    print(f"❌ Error al subir fondo visual {fondo}: {e}")
            else:
                print(f"⚠️ Fondo visual no encontrado: {fondo}")

    print("🧠 session['modo_admin']:", session.get('modo_admin'))
    print("🧠 modo_admin:", modo_admin)
    print("🧠 modo_admin_intentado:", modo_admin_intentado)
    print("🧠 session completa:", dict(session))

    try:
        return render_template(
            'preview.html',
            config=config,
            grupos=grupos_dict,
            modoAdmin=modo_admin,
            modoAdminIntentado=modo_admin_intentado,
            firebase_config=firebase_config
        )
    except Exception as e:
        import traceback
        print("🔥 Error renderizando preview.html:", e)
        traceback.print_exc()
        return "Internal Server Error al renderizar preview", 500


@app.route('/descargar')
def descargar():
    email = session.get('email')
    if not email:
        print("❌ Sesión no iniciada")
        return "Error: sesión no iniciada", 403

    estilo_visual = session.get('estilo_visual') or 'claro_moderno'

    # 🔄 Obtener productos desde Firestore
    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        productos_docs = productos_ref.stream()
        productos = [doc.to_dict() for doc in productos_docs]
        print(f"📦 Productos cargados desde Firestore: {len(productos)}")
    except Exception as e:
        print("❌ Error al obtener productos:", e)

    # 🧱 Agrupar por grupo y subgrupo
    grupos = {}
    for producto in productos:
        grupo = producto.get('grupo', 'General').strip().title()
        subgrupo = producto.get('subgrupo', 'Sin subgrupo').strip().title()
        if grupo not in grupos:
            grupos[grupo] = {}
        if subgrupo not in grupos[grupo]:
            grupos[grupo][subgrupo] = []
        grupos[grupo][subgrupo].append(producto)

    # 🧠 Configuración visual
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
        for producto in productos:
            imagen = producto.get('imagen')
            if imagen:
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen)
                if os.path.exists(imagen_path):
                    zip_file.write(imagen_path, arcname='img/' + imagen)

        # ✅ Incluir logo si existe
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
