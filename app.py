from flask import Flask, render_template, redirect, session, send_file, url_for, jsonify, current_app, request, flash
import requests
import os
import uuid
import re
import time
import json
import gc
import hashlib
import pandas as pd
import traceback
import boto3
from botocore.config import Config
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
from google.cloud.firestore import ArrayUnion
from flask_talisman import Talisman
from google.auth.transport.requests import Request
import builtins
from correo_argentino import (
    validar_credenciales, crear_orden, cancelar_orden,
    obtener_rotulos, consultar_historial, obtener_sucursales
)

##################
# 🔐 Inicialización segura de Firebase con logs
db = None
try:
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

    if cred_json:
        cred_dict = json.loads(cred_json)

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()

except Exception as e:
    import traceback
    db = None
###################
# Verificación final del cliente Firestore
if db:
    try:
        db.collection("_debug").document("conexion").get()
    except Exception:
        pass
####################
# 🔑 Inicialización segura de Mercado Pago
access_token = os.getenv("MERCADO_PAGO_TOKEN")
if access_token and isinstance(access_token, str):
    sdk = mercadopago.SDK(access_token.strip())
else:
    sdk = None
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
csp = {
    'default-src': ["'self'"],
    'style-src': [
        "'self'",
        "https://fonts.googleapis.com",  
        "https://cdn.jsdelivr.net",       
        "'unsafe-inline'"                 
    ],
    'script-src': [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",       
        "https://sdk.mercadopago.com",    
        "https://storage.googleapis.com"   
    ],
    'img-src': [
        "'self'",
        "data:",      
        "blob:",
        "https://storage.googleapis.com",  
        "https://raw.githubusercontent.com", 
        "https://*.cloudinary.com",        
        "https://*.fbcdn.net",        
        "https://*.r2.cloudflarestorage.com",
        "https://*.r2.dev",
        "https://*.instagram.com"          
    ],
    'font-src': [
        "'self'",
        "https://fonts.gstatic.com"       
    ],
    'connect-src': [
        "'self'",
        "https://mpagina.onrender.com",    
        "https://api.mercadopago.com",     
        "https://storage.googleapis.com",  
        "https://cdn.jsdelivr.net", 
        "https://*.r2.cloudflarestorage.com",
        "https://*.r2.dev",
        "https://*.onrender.com" 
    ],
    'frame-src': [
        "'self'",
        "https://www.mercadopago.com.ar"   
    ]
}

s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('R2_ENDPOINT_URL'),
    aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

Talisman(
    app,
    content_security_policy=csp,
    content_security_policy_nonce_in=[], 
    force_https=True,               
    frame_options='DENY',               
    strict_transport_security=True,    
    strict_transport_security_max_age=31536000, 
    strict_transport_security_include_subdomains=True,
    strict_transport_security_preload=True,
    x_content_type_options=True,  
    x_xss_protection=True                 
)
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

# 🔧 Configuración de la API de Correo Argentino (MiCorreo)
CA_MICORREO_TEST_URL = os.getenv("CA_MICORREO_TEST_URL", "https://apitest.correoargentino.com.ar/micorreo/v1")
CA_MICORREO_PROD_URL = os.getenv("CA_MICORREO_PROD_URL", "https://api.correoargentino.com.ar/micorreo/v1")

# Inicializar un diccionario para cachear el token en memoria (opcional)
ca_token_cache = {
    "token": None,
    "expires_at": None
}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/ca/cotizar', methods=['POST'])
def ca_cotizar():
    data = request.get_json(force=True)
    email_vendedor = data.get('email_vendedor') or session.get('email')
    if not email_vendedor:
        return jsonify({'error': 'Falta email del vendedor'}), 400
    
    codigo_postal_destino = data.get('codigo_postal_destino')
    peso_kg = data.get('peso_kg')
    alto_cm = data.get('alto_cm')
    ancho_cm = data.get('ancho_cm')
    largo_cm = data.get('largo_cm')

    if not all([codigo_postal_destino, peso_kg, alto_cm, ancho_cm, largo_cm]):
        return jsonify({'error': 'Faltan datos para la cotización'}), 400
    
    try:
        remitente_data = obtener_datos_remitente(email_vendedor, db)
        codigo_postal_origen = remitente_data["address"]["zipCode"]
        token = obtener_token_micorreo(email_vendedor)
        creds_doc = db.collection("usuarios").document(email_vendedor)\
                      .collection("config").document("correo_argentino").get()
        test_mode = creds_doc.to_dict().get("test_mode", True) if creds_doc.exists else True
        base_url = CA_MICORREO_TEST_URL if test_mode else CA_MICORREO_PROD_URL
        peso_volumetrico = (alto_cm * ancho_cm * largo_cm) / 5000
        peso_efectivo = max(peso_kg, peso_volumetrico)
        rates_url = f"{base_url}/rates"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "postalCodeOrigin": codigo_postal_origen,
            "postalCodeDestination": codigo_postal_destino,
            "deliveredType": "D",  
            "dimensions": {
                "weight": int(peso_efectivo * 1000),  
                "height": alto_cm,
                "width": ancho_cm,
                "length": largo_cm
            }
        }
        response = requests.post(rates_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data_response = response.json()
            rates = data_response.get('rates', [])
            if rates:
                costo = rates[0].get('price')
                return jsonify({
                    'ok': True,
                    'costo': costo,
                    'detalle': data_response
                })
            else:
                return jsonify({'ok': False, 'error': 'No se encontraron tarifas para los datos proporcionados'}), 400
        else:
            error_msg = f"Error en la API de MiCorreo: {response.status_code} - {response.text}"
            return jsonify({'ok': False, 'error': error_msg}), response.status_code
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
        
def obtener_token_micorreo(email_vendedor):
    creds_doc = db.collection("usuarios").document(email_vendedor)\
                  .collection("config").document("correo_argentino").get()
    
    if not creds_doc.exists:
        raise ValueError(f"El vendedor {email_vendedor} no ha configurado sus credenciales de Correo Argentino.")
    
    creds = creds_doc.to_dict()
    micorreo_user = creds.get("micorreo_user")
    micorreo_password = creds.get("micorreo_password")
    test_mode = creds.get("test_mode", True)

    if not micorreo_user or not micorreo_password:
        raise ValueError("Faltan el usuario o contraseña de MiCorreo en la configuración del vendedor.")

    base_url = CA_MICORREO_TEST_URL if test_mode else CA_MICORREO_PROD_URL
    token_url = f"{base_url}/token"
    cache_key = f"{email_vendedor}_token"
    cached_token = ca_token_cache.get(cache_key)
    
    if cached_token and cached_token.get("expires_at") > datetime.now():
        return cached_token["token"]
    
    try:
        response = requests.post(
            token_url,
            auth=(micorreo_user, micorreo_password),
            timeout=30
        )
        
        if response.status_code == 200:
            token_data = response.json()
            new_token = token_data.get("token")
            expires_str = token_data.get("expires")
            
            if not new_token:
                raise Exception("La respuesta de la API no contenía el campo 'token'")

            try:
                expires_at = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
            except:
                expires_at = datetime.now() + timedelta(minutes=30)

            ca_token_cache[cache_key] = {
                "token": new_token,
                "expires_at": expires_at
            }

            return new_token
        else:
            error_msg = f"Error al obtener token: {response.status_code} - {response.text}"
            raise Exception(error_msg)
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"No se pudo conectar con la API de MiCorreo: {e}")
    
@app.route('/ca/guardar-remitente', methods=['POST'])
def ca_guardar_remitente():
    data = request.get_json()
    email = session.get('email')
    if not email:
        return jsonify({'error': 'No autenticado'}), 401
    required = ['nombre', 'calle', 'altura', 'localidad', 'provincia_codigo', 'codigo_postal']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Falta {field}'}), 400
    db.collection('usuarios').document(email).collection('config').document('remitente').set(data, merge=True)
    return jsonify({'status': 'ok'})
    
def cotizar_envio(codigo_postal_origen, codigo_postal_destino, peso_kg, alto_cm, ancho_cm, largo_cm):
    token = obtener_token_micorreo()
    peso_volumetrico = (alto_cm * ancho_cm * largo_cm) / 5000
    peso_efectivo = max(peso_kg, peso_volumetrico)
    url = "https://api.correoargentino.com.ar/micorreo/v1/quote"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "origin_zipcode": codigo_postal_origen,
        "destination_zipcode": codigo_postal_destino,
        "weight": peso_efectivo,
        "service_type": "paq.ar",  
        "delivery_type": "homeDelivery"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("total_price")
    else:
        return None
        
@app.route('/ca/validar', methods=['POST'])
def ca_validar():
    """Valida las credenciales de Correo Argentino para el vendedor logueado."""
    data = request.get_json(silent=True) or {}
    email = data.get('email') or session.get('email')
    if not email:
        return jsonify({'error': 'No se especificó email'}), 400

    ok, msg = validar_credenciales(email, db)
    if ok:
        return jsonify({'status': 'ok', 'message': msg}), 200
    else:
        return jsonify({'status': 'error', 'message': msg}), 401

@app.route('/ca/crear-orden', methods=['POST'])
def ca_crear_orden():
    data = request.get_json(force=True)
    email = data.get('email') or session.get('email')
    if not email:
        return jsonify({'error': 'Falta email'}), 400

    orden_data = data.get('orden_data')
    if not orden_data:
        return jsonify({'error': 'Falta orden_data'}), 400

    success, tn, msg, status = crear_orden(email, db, orden_data)
    if success:
        return jsonify({'status': 'ok', 'trackingNumber': tn, 'message': msg}), 200
    else:
        return jsonify({'status': 'error', 'message': msg}), status

@app.route('/ca/cancelar-orden', methods=['POST'])
def ca_cancelar_orden():
    data = request.get_json(force=True)
    email = data.get('email') or session.get('email')
    tn = data.get('trackingNumber')
    if not email or not tn:
        return jsonify({'error': 'Faltan email o trackingNumber'}), 400

    success, msg, status = cancelar_orden(email, db, tn)
    return jsonify({'status': 'ok' if success else 'error', 'message': msg}), status

@app.route('/ca/rotulos', methods=['POST'])
def ca_rotulos():
    data = request.get_json(force=True)
    email = data.get('email') or session.get('email')
    pedidos = data.get('pedidos') 
    label_format = data.get('labelFormat') 
    if not email or not pedidos:
        return jsonify({'error': 'Faltan datos'}), 400

    success, result, status = obtener_rotulos(email, db, pedidos, label_format)
    if success:
        return jsonify(result), 200
    else:
        return jsonify({'error': result}), status

@app.route('/ca/historial', methods=['POST']) 
def ca_historial():
    data = request.get_json(force=True)
    email = data.get('email') or session.get('email')
    tracking_numbers = data.get('trackingNumbers')  # lista
    ext_client = data.get('extClient')
    if not email or not tracking_numbers:
        return jsonify({'error': 'Faltan datos'}), 400

    success, result, status = consultar_historial(email, db, tracking_numbers, ext_client)
    if success:
        return jsonify(result), 200
    else:
        return jsonify({'error': result}), status

@app.route('/ca/sucursales', methods=['GET'])
def ca_sucursales():
    email = request.args.get('email') or session.get('email')
    if not email:
        return jsonify({'error': 'Falta email'}), 400

    state_id = request.args.get('stateId')
    pickup = request.args.get('pickup_availability')
    if pickup is not None:
        pickup = pickup.lower() == 'true'
    package = request.args.get('package_reception')
    if package is not None:
        package = package.lower() == 'true'

    success, result, status = obtener_sucursales(email, db, state_id, pickup, package)
    if success:
        return jsonify(result), 200
    else:
        return jsonify({'error': result}), status

@app.route('/ca/guardar-credenciales', methods=['POST'])
def ca_guardar_credenciales():
    data = request.get_json()
    email = session.get('email')
    if not email:
        return jsonify({'error': 'No autenticado'}), 401
    
    agreement = data.get('agreement')
    api_key = data.get('api_key')
    test_mode = data.get('test_mode', True)
    micorreo_user = data.get('micorreo_user')
    micorreo_password = data.get('micorreo_password')
    
    if not agreement or not api_key:
        return jsonify({'error': 'Faltan agreement o api_key'}), 400
    if not micorreo_user or not micorreo_password:
        return jsonify({'error': 'Faltan usuario o contraseña de MiCorreo'}), 400
    
    db.collection('usuarios').document(email).collection('config').document('correo_argentino').set({
        'agreement': agreement,
        'api_key': api_key,
        'test_mode': test_mode,
        'micorreo_user': micorreo_user,
        'micorreo_password': micorreo_password,
        'updated_at': firestore.SERVER_TIMESTAMP
    }, merge=True)
    return jsonify({'status': 'ok'})
        

def subir_a_firestore(producto, email, es_edicion=False):
    try:
        if not isinstance(producto, dict):
            return {"status": "error", "error": "Producto inválido (no es dict)"}

        if not producto.get("nombre") or not producto.get("grupo") or not producto.get("precio"):
            return {"status": "error", "error": "Faltan campos obligatorios: nombre/grupo/precio"}

        id_base_existente = producto.get("id_base")
        
        if es_edicion and id_base_existente:
            custom_id = id_base_existente
            fecha = "EDITADO"
        else:
            grupo_original = producto["grupo"].strip()
            subgrupo_original = (producto.get("subgrupo", "") or "").strip() or f"General_{grupo_original}"
            nombre_original = producto["nombre"].strip()

            nombre_id = nombre_original.replace(" ", "_").lower()
            subgrupo_id = subgrupo_original.replace(" ", "_").lower()
            fecha = time.strftime("%Y%m%d")
            sufijo = uuid.uuid4().hex[:6]
            custom_id = f"{nombre_id}_{fecha}_{subgrupo_id}_{sufijo}"

        precio_anterior = 0
        if "precio_anterior" in producto:
            try:
                precio_anterior_raw = producto["precio_anterior"]
                if precio_anterior_raw:
                    precio_anterior_str = str(precio_anterior_raw).strip()
                    precio_anterior_clean = re.sub(r"[^\d,\.]", "", precio_anterior_str)

                    if "," in precio_anterior_clean and "." in precio_anterior_clean:
                        precio_anterior_clean = precio_anterior_clean.replace(".", "").replace(",", ".")
                    elif "," in precio_anterior_clean and "." not in precio_anterior_clean:
                        precio_anterior_clean = precio_anterior_clean.replace(",", ".")
                    
                    precio_anterior_float = float(precio_anterior_clean)
                    precio_anterior = int(round(precio_anterior_float))
                else:
                    precio_anterior = 0
            except Exception:
                precio_anterior = 0

        precio_actual = 0
        try:
            precio_raw = producto["precio"]
            price_str = str(precio_raw).strip()
            price_clean = re.sub(r"[^\d,\.]", "", price_str)

            if "," in price_clean and "." in price_clean:
                price_clean = price_clean.replace(".", "").replace(",", ".")
            elif "," in price_clean and "." not in price_clean:
                price_clean = price_clean.replace(",", ".")
            
            precio_actual_float = float(price_clean)
            precio_actual = int(round(precio_actual_float))
        except Exception as e:
            return {"status": "error", "error": f"Formato de precio inválido: '{price_str}' -> '{price_clean}'", "detail": str(e)}

        if precio_anterior > 0 and precio_anterior <= precio_actual:
            precio_anterior = 0

        fotos_adicionales = producto.get("fotos_adicionales", [])
        if not isinstance(fotos_adicionales, list):
            fotos_adicionales = []

        precio = precio_actual

        try:
            orden = int(producto.get("orden", 999))
        except Exception:
            orden = 999

        talles_input = producto.get("talles") or []
        if isinstance(talles_input, str):
            talles_input = [t.strip() for t in talles_input.split(',') if t.strip()]
        
        colores_input = producto.get("colores") or []
        if isinstance(colores_input, str):
            colores_input = [c.strip() for c in colores_input.split(',') if c.strip()]
        
        variantes_raw = producto.get("variantes") or {}
        stock_por_talle_input = producto.get("stock_por_talle") or {}

        tiene_variantes_input = producto.get("tiene_variantes", False)
        tiene_stock_por_talle_input = producto.get("tiene_stock_por_talle", False)

        imagen_url = producto.get("imagen_url")
        if not imagen_url:
            imagen_nombre = f"{custom_id}.webp"
            email_encoded = email.replace("@", "%40")
            imagen_url = f"https://storage.googleapis.com/mpagina/{email_encoded}/{imagen_nombre}"

        doc = {
            "nombre": producto.get("nombre", "").strip(),
            "id_base": custom_id,
            "precio": precio,
            "precio_anterior": precio_anterior,
            "grupo": producto.get("grupo", "").strip(),
            "subgrupo": (producto.get("subgrupo", "") or "").strip() or f"General_{producto.get('grupo', '').strip()}",
            "descripcion": producto.get("descripcion", ""),
            "imagen_url": imagen_url,
            "fotos_adicionales": fotos_adicionales,
            "orden": orden,
            "email_vendedor": email,
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        if tiene_variantes_input:
            variantes = {}
            for key, var in variantes_raw.items():
                variantes[key] = {
                    "talle": var.get("talle", ""),
                    "color": var.get("color", ""),
                    "stock": int(var.get("stock", 0)),
                    "imagen_url": var.get("imagen_url", "")
                }
            if not variantes and talles_input and colores_input:
                for talle in talles_input:
                    for color in colores_input:
                        key = f"{talle}_{color}".replace(" ", "_")
                        variantes[key] = {"talle": talle, "color": color, "stock": 0, "imagen_url": ""}
            
            doc["tiene_variantes"] = True
            doc["variantes"] = variantes
            doc["talles"] = talles_input
            doc["colores"] = colores_input
            doc["tiene_stock_por_talle"] = False
            doc["stock_por_talle"] = {}
            doc["stock"] = sum(v.get('stock', 0) for v in variantes.values())
        
        elif tiene_stock_por_talle_input:
            doc["tiene_stock_por_talle"] = True
            doc["stock_por_talle"] = stock_por_talle_input
            doc["talles"] = talles_input
            doc["tiene_variantes"] = False
            doc["variantes"] = {}
            doc["colores"] = []
            doc["stock"] = sum(stock_por_talle_input.values())
        
        else:
            doc["stock"] = int(producto.get("stock", 0))
            doc["tiene_variantes"] = False
            doc["variantes"] = {}
            doc["tiene_stock_por_talle"] = False
            doc["stock_por_talle"] = {}
            doc["talles"] = []
            doc["colores"] = []

        ruta = f"usuarios/{email}/productos/{custom_id}"
        if es_edicion:
            db.collection("usuarios").document(email).collection("productos").document(custom_id).set(doc, merge=True)
        else:
            db.collection("usuarios").document(email).collection("productos").document(custom_id).set(doc)
            
        update_products_last_modified(email)
        
        return {
            "status": "ok", 
            "ok": True, 
            "id_base": custom_id, 
            "tiene_variantes": doc["tiene_variantes"], 
            "tiene_stock_por_talle": doc["tiene_stock_por_talle"],
            "es_edicion": es_edicion,
            "fotos_adicionales_count": len(fotos_adicionales),
            "precio_anterior": precio_anterior,
            "tiene_oferta": precio_anterior > 0
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}

def generate_code_verifier():
    return secrets.token_urlsafe(100)

def generate_code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


@app.route('/verificar-stock', methods=['POST'])
def verificar_stock():
    try:
        data = request.get_json(force=True) or {}
        carrito = data.get('carrito', [])
        email_vendedor = data.get('email_vendedor')

        if not email_vendedor:
            return jsonify({'ok': False, 'error': 'Falta email del vendedor'}), 400
        if not carrito:
            return jsonify({'ok': False, 'error': 'Carrito vacío'}), 400

        faltantes = []
        stock_actualizado = {} 

        for item in carrito:
            id_base = item.get('id_base')
            talle = item.get('talle', 'unico')
            cantidad_solicitada = item.get('cantidad', 1)

            if not id_base:
                continue

            prod_ref = db.collection('usuarios').document(email_vendedor)\
                         .collection('productos').where('id_base', '==', id_base).limit(1).get()
            
            if not prod_ref:
                faltantes.append({
                    'id_base': id_base,
                    'nombre': item.get('nombre', 'Producto'),
                    'error': 'Producto no encontrado'
                })
                continue

            prod_data = prod_ref[0].to_dict()

            stock_disponible = 0
            if prod_data.get('tiene_variantes'):
                variantes = prod_data.get('variantes', {})
                for key, var in variantes.items():
                    if var.get('talle') == talle:
                        stock_disponible = var.get('stock', 0)
                        break
            elif prod_data.get('stock_por_talle'):
                stock_por_talle = prod_data.get('stock_por_talle', {})
                stock_disponible = stock_por_talle.get(talle, 0)
            else:
                stock_disponible = prod_data.get('stock', 0)

            stock_actualizado[f"{id_base}_{talle}"] = stock_disponible

            if stock_disponible < cantidad_solicitada:
                faltantes.append({
                    'id_base': id_base,
                    'nombre': item.get('nombre', 'Producto'),
                    'talle': talle,
                    'solicitado': cantidad_solicitada,
                    'disponible': stock_disponible
                })

        if faltantes:
            return jsonify({
                'ok': False,
                'error': 'Stock insuficiente',
                'faltantes': faltantes,
                'stock_actualizado': stock_actualizado
            }), 200 

        return jsonify({
            'ok': True,
            'mensaje': 'Stock verificado correctamente',
            'stock_actualizado': stock_actualizado
        })

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/authorize")
def authorize():
    flow = build_flow()
    code_verifier = generate_code_verifier()
    session['code_verifier'] = code_verifier
    code_challenge = generate_code_challenge(code_verifier)
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method='S256',
        access_type='offline'  
    )
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    try:
        flow = build_flow()
        code_verifier = session.get('code_verifier')
        if not code_verifier:
            return "❌ Error: code_verifier no encontrado en sesión", 400
        flow.fetch_token(
            authorization_response=request.url,
            code_verifier=code_verifier
        )
        creds = flow.credentials
        token_data = creds.to_json()
        db.collection("_tokens").document("gmail").set({
            "token": token_data,
            "actualizado": firestore.SERVER_TIMESTAMP
        })
        return "✅ Autorización completada y token guardado en Firestore"
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return f"❌ Error: {e}<br><pre>{tb}</pre>", 500

def get_gmail_service():
    doc = db.collection("_tokens").document("gmail").get()
    if not doc.exists:
        raise RuntimeError("No hay token guardado en Firestore")

    creds_json = doc.to_dict()["token"]
    creds = Credentials.from_authorized_user_info(json.loads(creds_json), SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            db.collection("_tokens").document("gmail").set({
                "token": creds.to_json(),
                "actualizado": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            raise
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
    doc = db.collection("short_links").document(short_id).get()
    if doc.exists:
        url_larga = doc.to_dict().get("url")
        return redirect(url_larga)
    else:
        return "Link no encontrado", 404
        
def subir_archivo(repo, contenido_bytes, ruta_remota, branch="main"):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        return {"ok": False, "error": "Token de GitHub no disponible"}

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo}/contents/{ruta_remota}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }
    sha = None
    try:
        r_get = requests.get(url, headers=headers, timeout=10)
        if r_get.status_code == 200:
            sha = r_get.json().get("sha")
    except Exception as e:
        sha = None

    data = {
        "message": f"Actualización automática de {ruta_remota}",
        "content": base64.b64encode(contenido_bytes).decode("utf-8"),
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    try:
        r = requests.put(url, headers=headers, json=data, timeout=10)
        if r.status_code in (200, 201):
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{repo}/{branch}/{ruta_remota}"
            html_url = r.json().get("content", {}).get("html_url")
            return {
                "ok": True,
                "url": html_url,
                "raw_url": raw_url,
                "status": r.status_code
            }
        else:
            return {"ok": False, "status": r.status_code, "error": r.text}
    except Exception as e:
        import traceback
        return {"ok": False, "error": str(e)}


@app.route("/subir-foto", methods=["POST"])
def subir_foto():
    try:
        file = request.files.get("file")
        email = request.form.get("email")

        if not file or not email:
            return jsonify({"ok": False, "error": "Falta archivo o email"}), 400

        if not allowed_file(file.filename):
            return jsonify({"ok": False, "error": "Formato inválido. Usa png/jpg/jpeg/webp"}), 400

        contenido_bytes = file.read()
        if len(contenido_bytes) > MAX_IMAGE_SIZE_BYTES:
            return jsonify({"ok": False, "error": "Imagen excede 3 MB"}), 413

        imagen_original = Image.open(BytesIO(contenido_bytes)).convert('RGB')
        base_uuid = uuid.uuid4().hex
        email_safe = email.replace('@', '_at_').replace('.', '_dot_')

        def subir_version(tamaño, sufijo):
            img_copy = imagen_original.copy()
            img_copy.thumbnail((tamaño, tamaño), Image.Resampling.LANCZOS)
            canvas = Image.new('RGB', (tamaño, tamaño), (0, 0, 0))
            offset = ((tamaño - img_copy.width) // 2, (tamaño - img_copy.height) // 2)
            canvas.paste(img_copy, offset)
            buffer = BytesIO()
            canvas.save(buffer, format='WEBP', quality=80)
            buffer.seek(0)

            key = f"usuarios/{email_safe}/{base_uuid}_{sufijo}.webp"
            s3_client.put_object(
                Bucket=os.getenv('R2_BUCKET_NAME'),
                Key=key,
                Body=buffer.getvalue(),
                ContentType='image/webp',
                CacheControl='public, max-age=31536000'
            )
            public_url = os.getenv('R2_PUBLIC_URL')
            return f"{public_url}/{key}"

        url_500 = subir_version(500, '500')
        url_180 = subir_version(180, '180')
        url_58  = subir_version(58, '58')

        return jsonify({
            "ok": True,
            "url": url_500,
            "url_180": url_180,
            "url_58": url_58,
            "size": len(contenido_bytes)
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



def update_products_last_modified(email):
    try:
        doc_ref = db.collection('usuarios').document(email).collection('metadata').document('productos')
        doc_ref.set({'last_updated': firestore.SERVER_TIMESTAMP}, merge=True)
    except Exception as e:
        pass


def get_products_etag(email):
    try:
        doc = db.collection('usuarios').document(email).collection('metadata').document('productos').get()
        if doc.exists:
            data = doc.to_dict()
            ts = data.get('last_updated')
            if ts:
                if hasattr(ts, 'timestamp'):
                    return str(ts.timestamp())
                return str(ts)
    except Exception as e:
    return None


@app.route("/api/productos")
def api_productos():
    email = session.get("email") or request.args.get("usuario")
    if not email:
        return jsonify({"error": "No se especificó usuario"}), 403

    etag = get_products_etag(email)

    if etag:
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match and if_none_match == f'"{etag}"':
            return '', 304

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        docs = productos_ref.stream()

        productos = []
        for doc in docs:
            data = doc.to_dict() or {}

            if data.get("tiene_variantes", False):
                pass
            elif data.get("tiene_stock_por_talle", False):
                stock_pt = data.get("stock_por_talle", {})
                if "unico" in stock_pt:
                    variantes = {"unico_unico": {
                        "talle": "unico",
                        "color": "unico",
                        "stock": stock_pt["unico"],
                        "imagen_url": ""
                    }}
                    talles = ["unico"]
                    colores = ["unico"]
                else:
                    variantes = {}
                    talles = list(stock_pt.keys())
                    colores = ["General"]
                    for talle, stock in stock_pt.items():
                        key = f"{talle}_General".replace(" ", "_")
                        variantes[key] = {
                            "talle": talle,
                            "color": "General",
                            "stock": stock,
                            "imagen_url": ""
                        }
                data["tiene_variantes"] = True
                data["variantes"] = variantes
                data["talles"] = talles
                data["colores"] = colores
            else:
                stock_simple = data.get("stock", 0)
                variantes = {"unico_unico": {
                    "talle": "unico",
                    "color": "unico",
                    "stock": stock_simple,
                    "imagen_url": ""
                }}
                data["tiene_variantes"] = True
                data["variantes"] = variantes
                data["talles"] = ["unico"]
                data["colores"] = ["unico"]

            talles_originales = data.get("talles", [])
            if isinstance(talles_originales, str):
                talles_originales = [t.strip() for t in talles_originales.split(",") if t.strip()]
            elif not isinstance(talles_originales, list):
                talles_originales = []
            
            fotos_adicionales = data.get("fotos_adicionales", [])
            if not isinstance(fotos_adicionales, list):
                fotos_adicionales = []

            variantes = data.get("variantes", {})
            stock_por_talle_filtrado = {}
            stock_disponible = 0
            for var in variantes.values():
                talle = var.get("talle")
                if talle:
                    stock = var.get("stock", 0)
                    stock_por_talle_filtrado[talle] = stock_por_talle_filtrado.get(talle, 0) + stock
                    stock_disponible += stock
                else:
                    stock_disponible += var.get("stock", 0)

            if len(stock_por_talle_filtrado) == 1 and "unico" in stock_por_talle_filtrado:
                pass
            elif len(stock_por_talle_filtrado) == 0:
                stock_por_talle_filtrado = {"unico": 0}
                stock_disponible = 0
            
            disponible = stock_disponible > 0
            
            productos.append({
                "id": doc.id,
                "id_base": data.get("id_base"),
                "nombre": data.get("nombre"),
                "precio": data.get("precio"),
                "stock": stock_disponible,
                "stock_por_talle": stock_por_talle_filtrado,
                "disponible": disponible,
                "grupo": data.get("grupo"),
                "subgrupo": data.get("subgrupo"),
                "descripcion": data.get("descripcion"),
                "imagen_url": data.get("imagen_url"),
                "fotos_adicionales": fotos_adicionales,
                "precio_anterior": data.get("precio_anterior", 0),
                "orden": data.get("orden"),
                "talles": talles_originales,
                "colores": data.get("colores", []),
                "variantes": variantes,
                "tiene_variantes": data.get("tiene_variantes", True),
                "tiene_stock_por_talle": False, 
                "sistema_stock": "variantes_unificado",
                "timestamp": str(data.get("timestamp")) if data.get("timestamp") else None
            })

        productos = sorted(productos, key=lambda p: p.get("orden") or 0)

        response = jsonify(productos)
        if etag:
            response.set_etag(etag)
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
        
@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        email = session.get("email")
        if not email:
            return jsonify({"ok": False, "error": "No se ha iniciado sesión"}), 401

        imagenes = request.files.getlist('imagenes')
        if not imagenes:
            return jsonify({"ok": False, "error": "No se recibieron imágenes"}), 400

        if 'imagenes_step0' not in session:
            session['imagenes_step0'] = []

        urls_grandes = []  
        urls_medianas = []     
        urls_miniaturas = []   
        errores = []

        for img in imagenes:
            if not img or not img.filename:
                continue
            try:
                contenido_bytes = img.read()
                imagen_original = Image.open(BytesIO(contenido_bytes)).convert('RGB')
                base_uuid = uuid.uuid4().hex

                def subir_version(tamaño, sufijo):
                    img_copy = imagen_original.copy()
                    img_copy.thumbnail((tamaño, tamaño), Image.Resampling.LANCZOS)
                    canvas = Image.new('RGB', (tamaño, tamaño), (0, 0, 0))
                    offset = ((tamaño - img_copy.width) // 2, (tamaño - img_copy.height) // 2)
                    canvas.paste(img_copy, offset)
                    buffer = BytesIO()
                    canvas.save(buffer, format='WEBP', quality=80)
                    buffer.seek(0)
                    
                    email_safe = email.replace('@', '_at_').replace('.', '_dot_')  
                    key = f"usuarios/{email_safe}/{base_uuid}_{sufijo}.webp"
                    s3_client.put_object(
                        Bucket=os.getenv('R2_BUCKET_NAME'),
                        Key=key,
                        Body=buffer.getvalue(),
                        ContentType='image/webp',
                        CacheControl='public, max-age=31536000'
                    )
                    public_url = os.getenv('R2_PUBLIC_URL')
                    return f"{public_url}/{key}"
                    
                url_500 = subir_version(500, '500')
                url_180 = subir_version(180, '180')
                url_58  = subir_version(58, '58')

                urls_grandes.append(url_500)
                urls_medianas.append(url_180)
                urls_miniaturas.append(url_58)

                session['imagenes_step0'].append(url_500)
                session.modified = True

            except Exception as e:
                errores.append(f"Error con {img.filename}: {str(e)}")
                continue

        return jsonify({
            "ok": True,
            "imagenes": urls_grandes,
            "mediums": urls_medianas,
            "thumbs": urls_miniaturas,
            "errores": errores,
            "total": len(urls_grandes),
            "mensaje": f"Se subieron {len(urls_grandes)} imágenes. {len(errores)} fallos."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
        


def subir_iconos_webp(repo):
    carpeta = os.path.join("static", "img")
    iconos_webp = ["facebook.webp", "instagram.webp", "whatsapp.webp", "tik-tok.webp", "mercadopago.webp", "map.webp"]
    for nombre_archivo in iconos_webp:
        ruta_local = os.path.join(carpeta, nombre_archivo)
        if os.path.exists(ruta_local):
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
    return render_template('step0.html')


def get_mp_token(email: str):
    try:
        if email:
            doc_ref = db.collection("usuarios").document(email).collection("config").document("mercado_pago")
            snap = doc_ref.get()
            if snap.exists:
                data = snap.to_dict()
                token = data.get("access_token")
                if token and isinstance(token, str) and token.strip():
                    return token.strip()

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
                                doc_ref.set({"access_token": new_token}, merge=True)
                                return new_token.strip()
                    except Exception as e:
                        pass
    except Exception as e:
        pass

    token = os.getenv("MERCADO_PAGO_TOKEN")
    if token and isinstance(token, str):
        return token.strip()

    return None

@app.route('/success')
def pago_success():
    orden_id = request.args.get('orden_id')
    url_retorno = request.args.get('retorno')
    email_vendedor = request.args.get('email')
    
    if url_retorno:
        try:
            url_retorno_decoded = unquote(url_retorno) 
            params = f"pago=success&orden_id={orden_id}"
            if email_vendedor:
                params += f"&email={email_vendedor}"
            
            separator = '&' if '?' in url_retorno_decoded else '?'
            redirect_url = f"{url_retorno_decoded}{separator}{params}"

            return redirect(redirect_url)
        except Exception as e:
            pass
    
    if email_vendedor:
        return redirect(f"/preview?email={email_vendedor}&pago=success&orden_id={orden_id}")
    
    return "✅ Pago aprobado correctamente. ¡Gracias por tu compra!"

@app.route('/failure')
def failure():
    orden_id = request.args.get('orden_id')
    url_retorno = request.args.get('retorno')
    email_vendedor = request.args.get('email')
 
    if url_retorno:
        try:
            url_retorno_decoded = unquote(url_retorno)  
            params = f"pago=failure&orden_id={orden_id}"
            if email_vendedor:
                params += f"&email={email_vendedor}"
            
            separator = '&' if '?' in url_retorno_decoded else '?'
            redirect_url = f"{url_retorno_decoded}{separator}{params}"

            return redirect(redirect_url)
        except Exception as e:
            pass
    
    if email_vendedor:
        return redirect(f"/preview?email={email_vendedor}&pago=failure&orden_id={orden_id}")
    
    return redirect("/?pago_fallido=true")

@app.route('/pending')
def pending():
    orden_id = request.args.get('orden_id')
    url_retorno = request.args.get('retorno')
    email_vendedor = request.args.get('email')

    if url_retorno:
        try:
            url_retorno_decoded = unquote(url_retorno) 
            params = f"pago=pending&orden_id={orden_id}"
            if email_vendedor:
                params += f"&email={email_vendedor}"
            
            separator = '&' if '?' in url_retorno_decoded else '?'
            redirect_url = f"{url_retorno_decoded}{separator}{params}"

            return redirect(redirect_url)
        except Exception as e:
            pass
    
    if email_vendedor:
        return redirect(f"/preview?email={email_vendedor}&pago=pending&orden_id={orden_id}")
    
    return redirect("/?pago_pendiente=true")

@app.route("/comprobante/<orden_id>")
def comprobante(orden_id):
    import json
    from datetime import datetime

    doc = db.collection("ordenes").document(orden_id).get()
    
    if not doc.exists:
        return "❌ Orden no encontrada", 404
    
    data = doc.to_dict()
    
    cliente_nombre = data.get("cliente_nombre", "Cliente").strip()
    cliente_email = data.get("cliente_email", "Sin email").strip()
    cliente_telefono = data.get("cliente_telefono", "Sin teléfono").strip()
    email_vendedor = data.get("email_vendedor")
    productos_data = data.get("carrito") or data.get("items") or data.get("items_mp") or []

    if isinstance(productos_data, str):
        try:
            productos_data = json.loads(productos_data)
        except:
            productos_data = []
    
    total = 0
    productos = []
    
    for idx, p in enumerate(productos_data):
        try:
            if not isinstance(p, dict):
                continue

            nombre = p.get("title") or p.get("nombre") or p.get("name") or f"Producto {idx+1}"
            precio_raw = None
            for key in ["unit_price", "precio", "price", "unit_price"]:
                if key in p:
                    precio_raw = p[key]
                    break

            precio = 0.0
            if precio_raw is not None:
                if isinstance(precio_raw, (int, float)):
                    precio = float(precio_raw)
                elif isinstance(precio_raw, str):
                    limpio = precio_raw.replace('$', '').replace(',', '.').strip()
                    try:
                        precio = float(limpio)
                    except:
                        precio = 0.0
            else:
                precio = 0.0

            cantidad_raw = None
            for key in ["quantity", "cantidad", "qty"]:
                if key in p:
                    cantidad_raw = p[key]
                    break

            cantidad = 1
            if cantidad_raw is not None:
                if isinstance(cantidad_raw, (int, float)):
                    cantidad = int(cantidad_raw)
                elif isinstance(cantidad_raw, str):
                    try:
                        cantidad = int(cantidad_raw)
                    except:
                        cantidad = 1
            else:
                cantidad = 1

            talle = p.get("talle") or p.get("size") or ""
            color = p.get("color") or p.get("colour") or ""
            imagen_url = None

            for key in ["imagen_url", "image_url", "picture_url", "img_url"]:
                if key in p and p[key]:
                    imagen_url = p[key]
                    break

            if not imagen_url and email_vendedor:
                id_base = p.get("id_base") or p.get("id") or p.get("product_id")
                if id_base:
                    try:
                        prod_doc = db.collection("usuarios").document(email_vendedor)\
                                      .collection("productos").document(id_base).get()
                        if prod_doc.exists:
                            prod_data = prod_doc.to_dict()
                            imagen_url = prod_data.get("imagen_url")
                    except Exception:
                        pass

            if not imagen_url and email_vendedor and nombre:
                try:
                    productos_ref = db.collection("usuarios").document(email_vendedor)\
                                      .collection("productos")
                    query = productos_ref.where("nombre", "==", nombre).limit(1).get()
                    if query:
                        prod_data = query[0].to_dict()
                        imagen_url = prod_data.get("imagen_url")
                except Exception:
                    pass

            if imagen_url:
                if "cloudinary" in imagen_url or "res.cloudinary.com" in imagen_url:
                    if "/image/upload/" in imagen_url:
                        parts = imagen_url.split("/image/upload/")
                        if len(parts) == 2:
                            imagen_url = f"{parts[0]}/image/upload/w_300,h_180,c_fill/{parts[1]}"

                elif "firebasestorage.googleapis.com" in imagen_url:
                    imagen_url = f"{imagen_url}?alt=media"
            
            subtotal = precio * cantidad
            total += subtotal
            
            producto = {
                "nombre": nombre,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": subtotal,
                "imagen_url": imagen_url,
                "color": color, 
                "talle": talle
            }
            
            productos.append(producto)
            
        except Exception:
            continue

    orden_total = data.get("total")
    if orden_total:
        try:
            total = float(orden_total)
        except Exception:
            pass

    if len(productos) == 0:
        productos.append({
            "nombre": "Productos varios",
            "cantidad": 1,
            "precio": total if total > 0 else 1.0,
            "subtotal": total if total > 0 else 1.0,
            "imagen_url": "",
            "talle": ""
        })

    fecha_creacion = data.get("fecha_creacion") or data.get("timestamp") or datetime.now()
    if isinstance(fecha_creacion, datetime):
        fecha_str = fecha_creacion.strftime("%d/%m/%Y %H:%M")
    else:
        fecha_str = str(fecha_creacion)
    
    return render_template("comprobante.html",
                          orden_id=orden_id,
                          cliente_nombre=cliente_nombre,
                          cliente_email=cliente_email,
                          cliente_telefono=cliente_telefono,
                          productos=productos,
                          total=total,
                          fecha=fecha_str)


def enviar_comprobante(email_vendedor, orden_id):
    import json
    from datetime import datetime
    
    doc_ref = db.collection("ordenes").document(orden_id)
    doc = doc_ref.get()
    if not doc.exists:
        return False

    data = doc.to_dict()

    if data.get("comprobante_enviado"):
        return True

    cliente_nombre = data.get("cliente_nombre", "Cliente").strip()
    cliente_email = data.get("cliente_email", "").strip()
    cliente_telefono = data.get("cliente_telefono", "No especificado").strip()
    
    productos_data = data.get("carrito") or data.get("items") or data.get("items_mp") or []
    
    if isinstance(productos_data, str):
        try:
            productos_data = json.loads(productos_data)
        except:
            productos_data = []
    
    total = 0
    productos_procesados = []
    
    for idx, p in enumerate(productos_data):
        try:
            if not isinstance(p, dict):
                continue
            
            nombre = p.get("title") or p.get("nombre") or p.get("name") or f"Producto {idx+1}"
            
            precio_raw = None
            for key in ["unit_price", "precio", "price", "unit_price"]:
                if key in p:
                    precio_raw = p[key]
                    break
            
            precio = 0.0
            if precio_raw is not None:
                if isinstance(precio_raw, (int, float)):
                    precio = float(precio_raw)
                elif isinstance(precio_raw, str):
                    limpio = precio_raw.replace('$', '').replace(',', '.').strip()
                    try:
                        precio = float(limpio)
                    except:
                        precio = 0.0
            
            cantidad_raw = None
            for key in ["quantity", "cantidad", "qty"]:
                if key in p:
                    cantidad_raw = p[key]
                    break
            
            cantidad = 1
            if cantidad_raw is not None:
                if isinstance(cantidad_raw, (int, float)):
                    cantidad = int(cantidad_raw)
                elif isinstance(cantidad_raw, str):
                    try:
                        cantidad = int(cantidad_raw)
                    except:
                        cantidad = 1
            
            talle = p.get("talle") or p.get("size") or ""
            color = p.get("color") or p.get("colour") or ""
            imagen_url = p.get("imagen_url") or p.get("image_url") or ""
            
            if imagen_url and ("?" not in imagen_url or ("width=" not in imagen_url and "height=" not in imagen_url)):
                if "cloudinary" in imagen_url or "res.cloudinary.com" in imagen_url:
                    if "/image/upload/" in imagen_url:
                        parts = imagen_url.split("/image/upload/")
                        if len(parts) == 2:
                            imagen_url = f"{parts[0]}/image/upload/w_300,h_180,c_fill/{parts[1]}"
                elif "firebasestorage.googleapis.com" in imagen_url:
                    imagen_url = f"{imagen_url}?alt=media"
            
            subtotal = precio * cantidad
            total += subtotal
            
            producto_procesado = {
                "title": nombre,
                "unit_price": precio,
                "quantity": cantidad,
                "subtotal": subtotal,
                "talle": talle,
                "color": color, 
                "imagen_url": imagen_url
            }
            
            productos_procesados.append(producto_procesado)
            
        except Exception:
            continue
    
    orden_total = data.get("total")
    if orden_total:
        try:
            total = float(orden_total)
        except Exception:
            pass
    
    if len(productos_procesados) == 0:
        productos_procesados.append({
            "title": "Productos varios",
            "unit_price": total if total > 0 else 1.0,
            "quantity": 1,
            "subtotal": total if total > 0 else 1.0,
            "talle": "",
            "imagen_url": ""
        })
    
    comprobante_url = f"https://mpagina.onrender.com/comprobante/{orden_id}"
    
    fecha_creacion = data.get("fecha_creacion") or data.get("timestamp") or datetime.now()
    if isinstance(fecha_creacion, datetime):
        fecha_str = fecha_creacion.strftime("%d/%m/%Y %H:%M")
    else:
        fecha_str = str(fecha_creacion)

    try:
        service = get_gmail_service()
        
        html = render_template("comprobante_email.html",
                               cliente_nombre=cliente_nombre,
                               cliente_email=cliente_email,
                               cliente_telefono=cliente_telefono,
                               productos=productos_procesados,
                               total=total,
                               comprobante_url=comprobante_url,
                               orden_id=orden_id,
                               fecha_creacion=fecha_str)

        msg = MIMEText(html, "html")
        msg["Subject"] = f"💰 Nueva venta - Orden #{orden_id} - ${total:.2f}"
        msg["From"] = "ferj6009@gmail.com"
        msg["To"] = email_vendedor
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        
        doc_ref.update({
            "comprobante_enviado": True,
            "comprobante_enviado_fecha": firestore.SERVER_TIMESTAMP,
            "productos_procesados": productos_procesados,
            "actualizado": firestore.SERVER_TIMESTAMP
        })
        
        return True
        
    except Exception as e:
        return False

@app.route("/webhook_mp", methods=["POST"])
def webhook_mp():
    evento = request.get_json(force=True) or {}
    
    payment_id = None
    if "data" in evento and isinstance(evento["data"], dict):
        payment_id = evento["data"].get("id")
    elif "id" in evento:
        payment_id = evento.get("id")
    
    if not payment_id:
        return jsonify({"ok": False}), 400
    
    access_token = os.getenv("MERCADO_PAGO_TOKEN")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        r = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", 
                        headers=headers, timeout=15)
        detalle = r.json()
        
        if r.status_code != 200:
            return jsonify({"ok": False}), 500
        
        external_ref = detalle.get("external_reference")
        if not external_ref:
            return jsonify({"ok": False}), 400
        
        estado = detalle.get("status")
        
        doc_ref = db.collection("ordenes").document(external_ref)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({"ok": False}), 404
        
        orden_data = doc.to_dict()

        todos_items = orden_data.get("carrito") or orden_data.get("items_mp") or orden_data.get("items") or []

        if estado == "approved":
            email_vendedor = orden_data.get("email_vendedor")
            cliente_nombre = orden_data.get("cliente_nombre", "")
            total_final = orden_data.get("total", 0)
            cliente_direccion = orden_data.get("cliente_direccion", {})
            
            if email_vendedor:
                for item in todos_items:
                    try:
                        if not isinstance(item, dict):
                            continue
                            
                        producto_id = item.get("id_base")
                        if not producto_id:
                            continue
                        
                        cantidad = int(item.get("cantidad", 1))
                        talle = item.get("talle", "")
                        color = item.get("color", "")

                        if not talle and not color:
                            title = item.get("title", "") or item.get("nombre", "") or ""
                            import re
                            talle_match = re.search(r"[Tt]alle[:\s]*([A-Za-z0-9]+)", title)
                            color_match = re.search(r"[Cc]olor[:\s]*([A-Za-z\s]+)", title)
                            if talle_match:
                                talle = talle_match.group(1).strip()
                            if color_match:
                                color = color_match.group(1).strip()
                            if not talle and not color:
                                parts = title.split('-')
                                if len(parts) >= 3:
                                    talle = parts[-2].strip()
                                    color = parts[-1].strip()
                            if not talle:
                                talle = item.get("metadata", {}).get("talle", "") or item.get("metadata", {}).get("size", "")
                            if not color:
                                color = item.get("metadata", {}).get("color", "") or item.get("metadata", {}).get("colour", "")
                        
                        talle = str(talle).strip()
                        color = str(color).strip()
                        
                        prod_ref = db.collection("usuarios").document(email_vendedor)\
                                      .collection("productos").document(producto_id)
                        prod_doc = prod_ref.get()
                        
                        if prod_doc.exists:
                            data = prod_doc.to_dict()
                            tiene_variantes = data.get("tiene_variantes", False)
                            variantes = data.get("variantes", {})
                            
                            if tiene_variantes and variantes and talle and color:
                                variante_encontrada = None
                                variante_key_encontrada = None
                                variante_key_exacta = f"{talle}_{color}".replace(" ", "_")
                                if variante_key_exacta in variantes:
                                    variante_encontrada = variantes[variante_key_exacta]
                                    variante_key_encontrada = variante_key_exacta
                                else:
                                    for key, variante in variantes.items():
                                        variante_talle = variante.get("talle", "").lower().strip()
                                        variante_color = variante.get("color", "").lower().strip()
                                        if (variante_talle == talle.lower() and 
                                            variante_color == color.lower()):
                                            variante_encontrada = variante
                                            variante_key_encontrada = key
                                            break
                                
                                if variante_encontrada and variante_key_encontrada:
                                    stock_variante = variante_encontrada.get("stock", 0)
                                    nuevo_stock_variante = max(0, stock_variante - cantidad)
                                    prod_ref.update({
                                        f"variantes.{variante_key_encontrada}.stock": nuevo_stock_variante
                                    })
                                    historial_ref = db.collection("usuarios").document(email_vendedor)\
                                                       .collection("productos").document(producto_id)\
                                                       .collection("stock_historial").document(f"{external_ref}_{variante_key_encontrada}")
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
                                        "variante_key": variante_key_encontrada,
                                        "nombre_producto": data.get("nombre", "")
                                    })
                                else:
                                    stock_actual = data.get("stock", 0)
                                    nuevo_stock = max(0, stock_actual - cantidad)
                                    prod_ref.update({"stock": nuevo_stock})
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
                                stock_actual = data.get("stock", 0)
                                nuevo_stock = max(0, stock_actual - cantidad)
                                prod_ref.update({"stock": nuevo_stock})
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
                            
                            try:
                                prod_doc_actualizado = prod_ref.get()
                                if prod_doc_actualizado.exists:
                                    data_actualizado = prod_doc_actualizado.to_dict()
                                    variantes_actualizadas = data_actualizado.get("variantes", {})
                                    if variantes_actualizadas:
                                        stock_total_actualizado = sum(v.get('stock', 0) for v in variantes_actualizadas.values())
                                        prod_ref.update({"stock": stock_total_actualizado})
                            except Exception:
                                pass
                        else:
                            nombre_producto = item.get("nombre") or item.get("title", "")
                            if nombre_producto:
                                try:
                                    query = db.collection("usuarios").document(email_vendedor)\
                                              .collection("productos").where("nombre", "==", nombre_producto).get()
                                    for prod_doc in query:
                                        prod_data = prod_doc.to_dict()
                                        stock_actual_real = prod_data.get("stock", 0)
                                        nuevo_stock_real = max(0, stock_actual_real - cantidad)
                                        prod_doc.reference.update({"stock": nuevo_stock_real})
                                        break
                                except Exception:
                                    pass
                    except Exception as e:
                        continue
                try:

                    remitente_data = obtener_datos_remitente(email_vendedor, db)
                    destinatario_data = {
                        "name": cliente_nombre,
                        "address": {
                            "streetName": cliente_direccion.get("calle", ""),
                            "streetNumber": cliente_direccion.get("numero", ""),
                            "cityName": cliente_direccion.get("localidad", ""),
                            "state": cliente_direccion.get("provincia_codigo", ""),
                            "zipCode": cliente_direccion.get("codigo_postal", "")
                        }
                    }
                    
                    peso_total = 0
                    for item in todos_items:
                        peso_item = item.get("peso_gramos", 500)
                        try:
                            peso_total += int(peso_item) * int(item.get("cantidad", 1))
                        except:
                            peso_total += 500 * int(item.get("cantidad", 1))

                    orden_ca = {
                        "sellerId": email_vendedor,
                        "order": {
                            "senderData": remitente_data,
                            "shippingData": destinatario_data,
                            "parcels": [{
                                "dimensions": {"height": "10", "width": "15", "depth": "20"},
                                "productWeight": str(peso_total),
                                "declaredValue": str(total_final)
                            }],
                            "deliveryType": "homeDelivery",
                            "saleDate": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
                            "serviceType": "CP"
                        }
                    }
                    
                    success_ca, tn, msg_ca, _ = crear_orden(email_vendedor, db, orden_ca)
                    if success_ca:
                        doc_ref.update({
                            "correo_argentino_tracking": tn,
                            "correo_argentino_creado": True,
                            "correo_argentino_respuesta": msg_ca
                        })
                    else:
                        doc_ref.update({
                            "correo_argentino_error": msg_ca,
                            "correo_argentino_intento": firestore.SERVER_TIMESTAMP
                        })
                except Exception as e:
                    doc_ref.update({
                        "correo_argentino_error": str(e),
                        "correo_argentino_intento": firestore.SERVER_TIMESTAMP
                    })

        update_data = {
            "estado": estado,
            "payment_id": payment_id,
            "actualizado": firestore.SERVER_TIMESTAMP,
            "webhook_processed": True,
            "webhook_timestamp": firestore.SERVER_TIMESTAMP,
            "stock_actualizado": estado == "approved",
            "stock_actualizado_fecha": firestore.SERVER_TIMESTAMP if estado == "approved" else None
        }
        
        if estado == "approved":
            update_data["pago_aprobado_fecha"] = firestore.SERVER_TIMESTAMP
            if len(todos_items) > 0:
                update_data["items_procesados"] = True
                update_data["items_procesados_fecha"] = firestore.SERVER_TIMESTAMP
        
        doc_ref.update(update_data)

        if estado == "approved":
            email_vendedor = orden_data.get("email_vendedor")
            if email_vendedor and not orden_data.get("comprobante_enviado", False):
                if enviar_comprobante(email_vendedor, external_ref):
                    doc_ref.update({
                        "comprobante_enviado": True,
                        "comprobante_enviado_fecha": firestore.SERVER_TIMESTAMP
                    })
                else:
                    pass
        
        return jsonify({"ok": True})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False}), 500


def obtener_datos_remitente(email, db):

    doc = db.collection("usuarios").document(email).collection("config").document("remitente").get()
    if not doc.exists:
        raise ValueError(f"Faltan datos del remitente para {email}. Configúralos en el panel.")
    data = doc.to_dict()

    required = ["nombre", "calle", "altura", "localidad", "provincia_codigo", "codigo_postal"]
    for field in required:
        if not data.get(field):
            raise ValueError(f"Falta el campo '{field}' en los datos del remitente")
    return {
        "name": data["nombre"],
        "address": {
            "streetName": data["calle"],
            "streetNumber": data["altura"],
            "cityName": data["localidad"],
            "state": data["provincia_codigo"],
            "zipCode": data["codigo_postal"]
        }
    }


@app.route('/actualizar-stock-talle', methods=['POST'])
def actualizar_stock_talle():
    try:
        data = request.json
        id_base = data.get('id') or data.get('id_base') 
        talle = data.get('talle')
        nuevo_stock = data.get('stock')
        email = data.get('email')  
        
        if not all([id_base, talle, nuevo_stock is not None, email]):
            return jsonify({'error': 'Faltan datos'}), 400

        producto_ref = db.collection('usuarios').document(email).collection('productos').document(id_base)
        producto = producto_ref.get()
        
        if not producto.exists:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        producto_data = producto.to_dict()
        stock_por_talle = producto_data.get('stock_por_talle', {})

        if not stock_por_talle and producto_data.get('talles'):
            for t in producto_data.get('talles', []):
                stock_por_talle[t] = 0

        stock_por_talle[talle] = nuevo_stock
        stock_total = sum(stock_por_talle.values())
        producto_ref.update({
            'stock_por_talle': stock_por_talle,
            'actualizado': firestore.SERVER_TIMESTAMP,
            'tiene_stock_por_talle': True 
        })

        update_products_last_modified(email)
        
        return jsonify({
            'status': 'ok',
            'id_base': id_base,
            'talle': talle,
            'stock': nuevo_stock,
            'stock_total': stock_total,
            'stock_por_talle': stock_por_talle
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/guardar-talles-stock', methods=['POST'])
def guardar_talles_stock():
    try:
        data = request.json
        id_base = data.get('id') or data.get('id_base')
        stock_por_talle = data.get('stock_por_talle')
        email = data.get('email')
        
        if not all([id_base, stock_por_talle, email]):
            return jsonify({'error': 'Faltan datos'}), 400

        if not isinstance(stock_por_talle, dict):
            return jsonify({'error': 'stock_por_talle debe ser un objeto JSON'}), 400

        producto_ref = db.collection('usuarios').document(email).collection('productos').document(id_base)
        producto = producto_ref.get()
        
        if not producto.exists:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        producto_data = producto.to_dict()
        
        stock_total = 0
        stock_por_talle_validado = {}
        
        for talle, stock in stock_por_talle.items():
            if talle and talle.strip():
                talle_limpio = talle.strip()
                try:
                    stock_int = int(stock) if stock is not None else 0
                    if stock_int < 0:
                        stock_int = 0
                    stock_por_talle_validado[talle_limpio] = stock_int
                    stock_total += stock_int
                except (ValueError, TypeError) as e:
                    pass

        talles_actualizados = list(stock_por_talle_validado.keys())
        update_data = {
            'stock_por_talle': stock_por_talle_validado,
            'talles': talles_actualizados,
            'actualizado': firestore.SERVER_TIMESTAMP,
            'tiene_stock_por_talle': True 
        }
        
        if producto_data.get('tiene_variantes'):
            update_data['tiene_variantes'] = False
            update_data['variantes'] = {}  

        producto_ref.update(update_data)

        update_products_last_modified(email)
        
        return jsonify({
            'status': 'ok',
            'id_base': id_base,
            'stock_total': stock_total,
            'talles': talles_actualizados,
            'stock_por_talle': stock_por_talle_validado
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
     
@app.route('/pagar', methods=['POST'])
def pagar():
    if not db:
        return jsonify({'error': 'Firestore no disponible'}), 503

    try:
        data = request.get_json(silent=True) or {}
        
        carrito = data.get('carrito', [])
        items_mp = data.get('items_mp', [])
        email_vendedor = data.get('email_vendedor')
        numero_vendedor = data.get('numero_vendedor', '')
        cliente_nombre = data.get('cliente_nombre')
        cliente_email = data.get('cliente_email')
        cliente_telefono = data.get('cliente_telefono', '')
        cliente_direccion = data.get('cliente_direccion', {})  
        orden_id = data.get('orden_id')
        total_recibido = data.get('total', 0)
        url_retorno = data.get('url_retorno')
        costo_envio = data.get('costo_envio', 0)  

        if not cliente_direccion.get('codigo_postal'):
        
        if not email_vendedor:
            return jsonify({'error': 'Falta email del vendedor'}), 400
        
        if not carrito and not items_mp:
            return jsonify({'error': 'Carrito vacío'}), 400
        
        if orden_id and orden_id.strip() and orden_id.startswith('ORD_'):
            external_ref = orden_id.strip()
        else:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            external_ref = f"ORD_{timestamp}_{shortuuid.uuid()[:8]}"
        
        access_token = get_mp_token(email_vendedor)
        if not access_token or not isinstance(access_token, str):
            return jsonify({'error': 'Vendedor sin credenciales MP válidas'}), 400
        
        sdk = mercadopago.SDK(access_token.strip())

        if items_mp and len(items_mp) > 0:
            items_para_mp = items_mp
            for item in items_para_mp:
                if not item.get('id') and not item.get('id_base'):
                    for item_carrito in carrito:
                        nombre_carrito = item_carrito.get('nombre', '')
                        titulo_item = item.get('title', '')
                        if nombre_carrito and titulo_item and nombre_carrito in titulo_item:
                            item['id'] = item_carrito.get('id_base', '')
                            item['id_base'] = item_carrito.get('id_base', '')
                            break
                
                if 'metadata' not in item and (item.get('talle') or item.get('color')):
                    metadata_item = {
                        "id_base": item.get('id_base', item.get('id', '')),
                        "nombre": item.get('title', 'Producto')
                    }
                    if item.get('talle'):
                        metadata_item["talle"] = item.get('talle')
                    if item.get('color'):
                        metadata_item["color"] = item.get('color')
                    item["metadata"] = metadata_item
        else:
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
                    color = item.get('color', '')
                    id_base = item.get('id_base', '')
                    imagen_url = item.get("imagen_url", "")
                    
                    titulo = nombre
                    if talle:
                        titulo = f"{nombre} (Talle: {talle})"
                    if color and talle:
                        titulo = f"{nombre} (Talle: {talle}, Color: {color})"
                    elif color and not talle:
                        titulo = f"{nombre} (Color: {color})"
                    
                    item_mp = {
                        "id": id_base,
                        "id_base": id_base,
                        "title": titulo,
                        "description": nombre,
                        "quantity": cantidad,
                        "unit_price": precio,
                        "imagen_url": imagen_url,
                        "currency_id": "ARS"
                    }
                    
                    metadata_item = {
                        "id_base": id_base,
                        "nombre": nombre,
                        "precio": precio,
                        "cantidad": cantidad,
                        "talle": talle,
                        "color": color,
                        "imagen_url": imagen_url
                    }
                    if item.get('grupo'):
                        metadata_item["grupo"] = item.get('grupo')
                    if item.get('subgrupo'):
                        metadata_item["subgrupo"] = item.get('subgrupo')
                    
                    item_mp["metadata"] = metadata_item
                    items_para_mp.append(item_mp)
                    
                except Exception:
                    continue
        
        items_sin_id = [item for item in items_para_mp if not item.get('id')]
        if items_sin_id:
            for i, item in enumerate(items_sin_id):
                temp_id = f"temp_{external_ref}_{i}"
                item['id'] = temp_id
                item['id_base'] = temp_id
                if 'metadata' in item:
                    item['metadata']['id_base'] = temp_id
        
        if not items_para_mp:
            return jsonify({'error': 'No se pudieron procesar los productos para el pago'}), 400
        
        total_calculado = sum(item.get('unit_price', 0) * item.get('quantity', 1) for item in items_para_mp)
        total_final = max(total_calculado, float(total_recibido or 0))
        
        base_url = "https://mpagina.onrender.com"
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
                "cliente_direccion": cliente_direccion, 
                "url_retorno": url_retorno,
                "debug_items": len(items_para_mp)
            }
        }
        
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {}) or {}
        
        if not preference.get("id"):
            return jsonify({'error': 'No se pudo generar la preferencia de pago'}), 500

        orden_doc = {
            "email_vendedor": email_vendedor,
            "numero_vendedor": numero_vendedor,
            "cliente_nombre": cliente_nombre,
            "cliente_email": cliente_email,
            "cliente_telefono": cliente_telefono,
            "cliente_direccion": cliente_direccion,  
            "carrito": carrito,
            "items_mp": items_para_mp,
            "items": items_para_mp,
            "total": total_final,
            "costo_envio": costo_envio, 
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
                "ids_items": [item.get('id') for item in items_para_mp],
                "talles_items": [item.get('metadata', {}).get('talle', '') for item in items_para_mp],
                "colores_items": [item.get('metadata', {}).get('color', '') for item in items_para_mp]
            }
        }
        
        db.collection("ordenes").document(external_ref).set(orden_doc)
        
        pedido_data = {
            "cliente_nombre": cliente_nombre,
            "cliente_email": cliente_email,
            "cliente_telefono": cliente_telefono,
            "cliente_direccion": cliente_direccion,  
            "carrito": carrito,
            "items_mp": items_para_mp,
            "total": total_final,
            "costo_envio": costo_envio,
            "estado": "pendiente",
            "preference_id": preference.get("id"),
            "external_reference": external_ref,
            "fecha_creacion": firestore.SERVER_TIMESTAMP,
            "comprobante_enviado": False,
            "url_retorno": url_retorno
        }
        
        db.collection("usuarios").document(email_vendedor)\
          .collection("pedidos").document(external_ref).set(pedido_data)
        
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
                "tiene_items_mp": len(items_para_mp) > 0,
                "items_con_metadata": sum(1 for item in items_para_mp if 'metadata' in item)
            }
        }
        
        return jsonify(response_data)

    except Exception as e:
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
            safe_data = {
                "public_key": data.get("public_key"),
                "access_token": bool(data.get("access_token")),  
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
            expiration = datetime.utcnow() + timedelta(days=7)
            token = jwt.encode(
                {"email": usuario, "exp": expiration},
                app.secret_key,
                algorithm="HS256"
            )
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
        data = request.get_json(force=True) or {}
        email = data.get("email")
        producto = data.get("producto")
            
        if not email:
            return jsonify({"status": "error", "error": "Falta email"}), 403
        if not producto:
            return jsonify({"status": "error", "error": "Producto inválido"}), 400

        fotos_adicionales = producto.get("fotos_adicionales", [])
        id_base = producto.get("id_base")
        es_edicion = bool(id_base)

        tiene_variantes = bool(producto.get('tiene_variantes', False))
        variantes = producto.get('variantes', {})
        
        if tiene_variantes and variantes:
            stock_total_variantes = sum(v.get('stock', 0) for v in variantes.values())
            producto['stock'] = stock_total_variantes
        elif tiene_variantes and not variantes:
            talles = producto.get('talles', [])
            colores = producto.get('colores', [])
            if talles and colores and producto.get('stock', 0) > 0:
                num_variantes = len(talles) * len(colores)
                if num_variantes > 0:
                    stock_por_variante = producto.get('stock', 0) // num_variantes

        if es_edicion:
            productos_ref = db.collection('productos').where('id_base', '==', id_base).where('email_vendedor', '==', email)
            docs = list(productos_ref.stream())
            
            if not docs:
                resultado = subir_a_firestore(producto, email, es_edicion=True)
            else:
                doc_ref = docs[0].reference
                
                datos_actualizar = {
                    'nombre': producto.get('nombre'),
                    'precio': producto.get('precio'),
                    'descripcion': producto.get('descripcion', ''),
                    'talles': producto.get('talles', []),
                    'grupo': producto.get('grupo'),
                    'subgrupo': producto.get('subgrupo'),
                    'stock_por_talle': producto.get('stock_por_talle', {}),
                    'imagen_url': producto.get('imagen_url', ''),
                    'fotos_adicionales': producto.get('fotos_adicionales', []),
                    'fecha_actualizacion': firestore.SERVER_TIMESTAMP
                }
                
                if 'tiene_variantes' in producto:
                    datos_actualizar['tiene_variantes'] = producto.get('tiene_variantes')
                if 'variantes' in producto:
                    datos_actualizar['variantes'] = producto.get('variantes')
                if 'stock' in producto:
                    datos_actualizar['stock'] = producto.get('stock')
                
                doc_ref.update(datos_actualizar)
                update_products_last_modified(email)
                resultado = {
                    'id_base': id_base,
                    'accion': 'actualizado',
                    'fotos_adicionales_count': len(datos_actualizar['fotos_adicionales']),
                    'timestamp': firestore.SERVER_TIMESTAMP
                }
        else:
            if 'fotos_adicionales' not in producto:
                producto['fotos_adicionales'] = []
            resultado = subir_a_firestore(producto, email, es_edicion=es_edicion)

        response_data = {
            "status": "ok",
            "email": email,
            "producto_id": id_base or resultado.get('id_base'),
            "accion": "actualizado" if es_edicion else "creado",
            "fotos_adicionales_count": len(fotos_adicionales),
            "resultado": resultado
        }
        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'detalle': 'Revisa los logs del servidor'
        }), 500
        
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
            return jsonify({"status": "not_found", "id_base": id_base}), 404

        doc = query[0]
        doc.reference.delete()
        update_products_last_modified(email)
        return jsonify({"status": "ok", "id_base": id_base})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return jsonify({"status": "error", "error": str(e), "trace": tb}), 500
        
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
        else:
            pass
            
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
                talles = request.form.get(f"talles_{idx}", "").strip() 

                if grupo and subgrupo and cantidad > 0:
                    for n in range(1, cantidad+1):
                        filas.append({
                            "Grupo": grupo,
                            "Subgrupo": subgrupo,
                            "Producto": f"{subgrupo}{n}",
                            "Talles": talles
                        })

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
    imagenes_disponibles = session.get('imagenes_step0') or []

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
        colores = request.form.getlist('colores')
        stocks = request.form.getlist('stock')
        imagenes_elegidas = request.form.getlist('imagen_elegida')

        repo_name = session.get('repo_nombre') or "AppWeb"

        for i in range(len(nombres)):
            nombre = nombres[i].strip()
            precio = precios[i].strip()
            grupo = grupos[i].strip() or 'Sin grupo'
            subgrupo = subgrupos[i].strip() or 'Sin subgrupo'
            orden = ordenes[i].strip() or str(i + 1)
            
            talle_raw = talles[i].strip() if i < len(talles) else ''
            talle_lista = [t.strip() for t in talle_raw.split(',') if t.strip()]
            
            color_raw = colores[i].strip() if i < len(colores) else ''
            color_lista = [c.strip() for c in color_raw.split(',') if c.strip()]
            
            stock_raw = stocks[i] if i < len(stocks) else "0"
            
            stock_final = 0
            if stock_raw and str(stock_raw).strip():
                try:
                    stock_final = int(str(stock_raw).strip())
                    if stock_final < 0:
                        stock_final = 0
                except (ValueError, TypeError):
                    stock_final = 0
            else:
                stock_final = 0

            if not nombre or not precio or not grupo or not subgrupo:
                continue

            imagen_url = imagenes_elegidas[i].strip() if i < len(imagenes_elegidas) else ''
            imagen_para_guardar = None

            if not imagen_url:
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
                        continue

            stock_por_talle = {}
            tiene_stock_por_talle = False
            
            if talle_lista:
                tiene_stock_por_talle = True
                if talle_lista:
                    stock_por_talle_individual = stock_final // len(talle_lista) if len(talle_lista) > 0 else 0
                    for talle in talle_lista:
                        stock_por_talle[talle] = stock_por_talle_individual
            else:
                tiene_stock_por_talle = True
                stock_por_talle = {"unico": stock_final}

            stock_total = sum(stock_por_talle.values())
            
            variantes = {}
            tiene_variantes = False
            
            if talle_lista and color_lista:
                tiene_variantes = True
                num_variantes = len(talle_lista) * len(color_lista)
                if num_variantes > 0:
                    stock_por_variante = stock_total // num_variantes
                    for talle in talle_lista:
                        for color in color_lista:
                            key = f"{talle}_{color}".replace(" ", "_")
                            variantes[key] = {
                                "talle": talle,
                                "color": color,
                                "stock": stock_por_variante,
                                "imagen_url": ""
                            }
            
            bloque = {
                'nombre': nombre,
                'descripcion': descripciones[i],
                'precio': precio,
                'stock_por_talle': stock_por_talle,
                'tiene_stock_por_talle': tiene_stock_por_talle,
                'imagen_url': imagen_para_guardar,
                'grupo': grupo,
                'subgrupo': subgrupo,
                'orden': orden,
                'talles': talle_lista,
                'colores': color_lista,
                'variantes': variantes,
                'tiene_variantes': tiene_variantes
            }
            
            if tiene_stock_por_talle:
                bloque['stock'] = stock_total
            else:
                bloque['stock'] = stock_total
            
            bloques.append(bloque)

        session['bloques'] = bloques
        exitos = 0

        def subir_con_resultado(producto):
            try:
                resultado = subir_a_firestore(producto, email)
                if isinstance(resultado, dict):
                    return resultado.get("status") == "ok" or resultado.get("ok") == True
                else:
                    return bool(resultado)
            except Exception:
                return False

        bloques_por_lote = 10
        for inicio in range(0, len(bloques), bloques_por_lote):
            lote = bloques[inicio:inicio + bloques_por_lote]
            with ThreadPoolExecutor(max_workers=3) as executor:
                resultados = list(executor.map(subir_con_resultado, lote))
            exitos += sum(1 for r in resultados if r)

        grupos_dict = {}
        for producto in bloques:
            grupo = (producto.get('grupo') or 'General').strip().title()
            subgrupo = (producto.get('subgrupo') or 'Sin subgrupo').strip().title()
            grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(producto)

        if repo_name:
            try:
                html = render_template(
                    'preview.html',
                    config=session,
                    grupos=grupos_dict,
                    modoAdmin=False,
                    modoAdminIntentado=False,
                    firebase_config=firebase_config
                )
                subir_archivo(repo_name, html.encode('utf-8'), 'index.html')
            except Exception:
                pass

            robots_path = os.path.join(app.root_path, 'templates', 'robots.txt')
            if os.path.exists(robots_path):
                with open(robots_path, 'rb') as f:
                    subir_archivo(repo_name, f.read(), 'robots.txt')
            else:
                subir_archivo(repo_name, b"User-agent: *\nDisallow:\n", 'robots.txt')

            middleware_path = os.path.join(app.root_path, 'functions', '_middleware.js')
            if os.path.exists(middleware_path):
                with open(middleware_path, 'rb') as f:
                    subir_archivo(repo_name, f.read(), 'functions/_middleware.js')
                else:
                subir_archivo(repo_name, b'export async function onRequest(context) { return await context.next(); }', 'functions/_middleware.js')

            core_js_path = os.path.join(app.root_path, 'static', 'js', 'core.js')
            if os.path.exists(core_js_path):
                with open(core_js_path, 'rb') as f:
                    subir_archivo(repo_name, f.read(), 'static/js/core.js')
            else:
                pass
        
            bootstrap_css_path = os.path.join(app.root_path, 'static', 'css', 'bootstrap.min.css')
            if os.path.exists(bootstrap_css_path):
                with open(bootstrap_css_path, 'rb') as f:
                    subir_archivo(repo_name, f.read(), 'static/css/bootstrap.min.css')
            else:
                pass

            admin_js_path = os.path.join(app.root_path, 'static', 'js', 'admin.js')
            if os.path.exists(admin_js_path):
                with open(admin_js_path, 'rb') as f:
                    subir_archivo(repo_name, f.read(), 'static/js/admin.js')
            else:
                pass

            mercadopago_js_path = os.path.join(app.root_path, 'static', 'js', 'mercadopago.js')
            if os.path.exists(mercadopago_js_path):
                with open(mercadopago_js_path, 'rb') as f:
                    subir_archivo(repo_name, f.read(), 'static/js/mercadopago.js')
            else:
                pass

            try:
                css_path = os.path.join(app.root_path, 'static', 'css', 'estilos.min.css')
                if os.path.exists(css_path):
                    with open(css_path, 'rb') as f:
                        subir_archivo(repo_name, f.read(), 'static/css/estilos.min.css')
            except Exception:
                pass
    
            try:
                subir_iconos_webp(repo_name)
            except Exception:
                pass

            logo = session.get('logo')
            if logo:
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo)
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        contenido = f.read()
                    subir_archivo(repo_name, contenido, f"static/img/{logo}")

            estilo_visual = session.get('estilo_visual')
            fondo_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{estilo_visual}.jpeg")
            if os.path.exists(fondo_path):
                with open(fondo_path, "rb") as f:
                    contenido = f.read()
                subir_archivo(repo_name, contenido, f"static/img/{estilo_visual}.jpeg")

        if exitos > 0:
            session.pop('imagenes_step0', None)
            return redirect(f"/preview?email={email}&step3_completado=true&guardados={exitos}")
        else:
            return render_template(
                'step3.html',
                tipo_web=tipo,
                imagenes_step0=imagenes_disponibles,
                email=email,
                productos=bloques
            )

    return render_template(
        'step3.html',
        tipo_web=tipo,
        imagenes_step0=imagenes_disponibles,
        email=email
    )

def get_mp_public_key(email: str):
    try:
        if email:
            doc_ref = db.collection("usuarios").document(email).collection("config").document("mercado_pago")
            snap = doc_ref.get()
            if snap.exists:
                data = snap.to_dict()
                pk = data.get("public_key")
                if pk and isinstance(pk, str) and pk.strip():
                    return pk.strip()
                else:
                    pass
    except Exception as e:
        pass

    access_token = None
    try:
        access_token = get_mp_token(email)
    except Exception as e:
        pass

    public_key = None
    if access_token and isinstance(access_token, str):
        try:
            resp = requests.get(
                "https://api.mercadopago.com/v1/account/credentials",
                headers={"Authorization": f"Bearer {access_token.strip()}"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json() or {}
                public_key = (data.get("public_key") or data.get("web", {}).get("public_key") or "").strip()
        except Exception as e:
            pass

        if not public_key:
            try:
                resp = requests.get(
                    "https://api.mercadopago.com/users/me",
                    headers={"Authorization": f"Bearer {access_token.strip()}"},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json() or {}
                    public_key = (data.get("public_key") or "").strip()
            except Exception as e:
                pass

        if public_key:
            try:
                db.collection("usuarios").document(email).collection("config").document("mercado_pago").set({
                    "public_key": public_key,
                    "updated_at": datetime.now().isoformat()
                }, merge=True)
                return public_key
            except Exception as e:
                pass

    pk_env = os.getenv("MP_PUBLIC_KEY")
    if pk_env and isinstance(pk_env, str) and pk_env.strip():
        return pk_env.strip()

    return None

@app.route('/conectar_mp', methods=["GET"])
def conectar_mp():
    email = request.args.get("email")
    url_retorno = request.args.get("url_retorno")

    if not email:
        return "Error: falta email", 403

    try:
        doc_ref = db.collection("usuarios").document(email).collection("config").document("mercado_pago")
        snap = doc_ref.get()
        if not snap.exists:
            pass
        else:
            pass
    except Exception as e:
        return "Error interno", 500

    client_id = os.getenv("MP_CLIENT_ID")
    if not client_id:
        return "❌ Falta configurar MP_CLIENT_ID en entorno", 500

    redirect_uri = url_for("callback_mp", _external=True)
    state_data = f"{email}|{url_retorno or ''}"
    
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "read write offline_access",
        "state": state_data  
    })
    auth_url = f"https://auth.mercadopago.com/authorization?{query}"
    return redirect(auth_url)

@app.route('/callback_mp')
def callback_mp():
    code = request.args.get('code')
    state_data = request.args.get('state')

    if not state_data:
        return "Error: falta parámetro state", 403
    if not code:
        return "❌ No se recibió código de autorización", 400

    parts = state_data.split('|')
    email = parts[0] if len(parts) > 0 else ""
    url_retorno = parts[1] if len(parts) > 1 else None

    if url_retorno == "":
        url_retorno = None

    if not email:
        return "❌ Error: email no encontrado en state", 400

    client_id = os.getenv("MP_CLIENT_ID")
    client_secret = os.getenv("MP_CLIENT_SECRET")
    redirect_uri = url_for('callback_mp', _external=True)
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
            return "❌ Error al obtener token de Mercado Pago", 400

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
                pass

        if public_key and isinstance(public_key, str):
            public_key = public_key.strip()

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

        if url_retorno:
            destino = url_retorno.rstrip("/")

            if "?" in destino:
                redirect_url = f"{destino}&mp_configurado=true&email={email}"
            else:
                redirect_url = f"{destino}?mp_configurado=true&email={email}"

            return redirect(redirect_url)
        else:
            preview_url = f"https://mpagina.onrender.com/preview?email={email}&mp_configurado=true"
            return redirect(preview_url)

    except Exception as e:
        import traceback
        traceback.print_exc()

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
    email = request.args.get('email') or session.get("email")
    orden_id = request.args.get("orden_id")
    if not email:
        return "Error: falta email", 400

    try:
        config_doc = db.collection("usuarios").document(email).collection("config").document("general").get()
        config_data = config_doc.to_dict() if config_doc.exists else {}
    except Exception as e:
        config_data = {}

    estilo_visual = config_data.get("estilo_visual", "claro_moderno")

    productos = []
    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        for doc in productos_ref.stream():
            data = doc.to_dict()

            tiene_variantes = data.get('tiene_variantes', False)
            variantes = data.get('variantes', {})
            
            if tiene_variantes and variantes:
                stock_total = sum(v.get('stock', 0) for v in variantes.values())
                disponible = stock_total > 0
            else:
                stock_total = data.get('stock', 0)
                disponible = stock_total > 0
            
            data['stock_total'] = stock_total
            data['disponible'] = disponible
            
            productos.append(data)
            
        productos = sorted(productos, key=lambda p: p.get('orden', 0))
    except Exception as e:
        pass

    grupos_dict = {}
    for p in productos:
        grupo = (p.get('grupo') or 'General').strip().title()
        subgrupo = (p.get('subgrupo') or 'Sin Subgrupo').strip().title()
        grupos_dict.setdefault(grupo, {}).setdefault(subgrupo, []).append(p)

    mercado_pago_token = get_mp_token(email)
    public_key = (get_mp_public_key(email) or "").strip()

    config = {
        **config_data,
        'email': email,
        'orden_id': orden_id,
        'estilo_visual': estilo_visual,
        'mercado_pago': bool(mercado_pago_token),
        'public_key': public_key,
        'productos': productos,
        'usarFirestore': True
    }

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

    try:
        productos_ref = db.collection("usuarios").document(email).collection("productos")
        productos_docs = productos_ref.stream()
        productos = [doc.to_dict() for doc in productos_docs]
    except Exception as e:
        productos = []

    grupos = {}
    for producto in productos:
        grupo = (producto.get('grupo', 'General').strip().title())
        subgrupo = (producto.get('subgrupo', 'Sin subgrupo').strip().title())
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
            imagen_url = producto.get('imagen_github')
            if not imagen_url:
                continue

            if imagen_url.startswith("http"):  
                try:
                    r = requests.get(imagen_url, timeout=10)
                    if r.status_code == 200:
                        filename = os.path.basename(imagen_url)
                        zip_file.writestr("img/" + filename, r.content)
                except Exception as e:
                    pass
            else:  
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(imagen_url))
                if os.path.exists(imagen_path):
                    zip_file.write(imagen_path, arcname="img/" + os.path.basename(imagen_url))

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
