import requests
import os
from flask import current_app, jsonify
from google.cloud.firestore import SERVER_TIMESTAMP

# Configuración desde variables de entorno (fallback)
CA_TEST_URL = os.getenv("CA_TEST_URL", "https://apitest.correoargentino.com.ar/paqar/v1")
CA_PROD_URL = os.getenv("CA_PROD_URL", "https://api.correoargentino.com.ar/paqar/v1")
CA_AGREEMENT = os.getenv("CA_AGREEMENT")
CA_API_KEY = os.getenv("CA_API_KEY")

def get_ca_credentials(email, db):
    """Obtiene agreement y api_key desde Firestore para un vendedor."""
    doc_ref = db.collection("usuarios").document(email).collection("config").document("correo_argentino")
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        return data.get("agreement"), data.get("api_key"), data.get("test_mode", True)
    # Fallback a variables de entorno
    return CA_AGREEMENT, CA_API_KEY, True

def _request(method, endpoint, email, db, body=None, params=None, label_format=None):
    """Función interna para hacer requests a la API de CA."""
    agreement, api_key, test_mode = get_ca_credentials(email, db)
    if not agreement or not api_key:
        raise ValueError(f"Faltan credenciales de Correo Argentino para {email}")

    base_url = CA_TEST_URL if test_mode else CA_PROD_URL
    url = f"{base_url}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Apikey {api_key}",
        "agreement": agreement,
        "Content-Type": "application/json"
    }
    if label_format:
        params = params or {}
        params["labelFormat"] = label_format

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=body,
        params=params,
        timeout=30
    )
    return response

def validar_credenciales(email, db):
    """GET /v1/auth -> 204 si ok, else error."""
    try:
        resp = _request("GET", "auth", email, db)
        if resp.status_code == 204:
            return True, "Credenciales válidas"
        else:
            return False, f"Error {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)

def crear_orden(email, db, orden_data):
    """
    POST /v1/orders
    orden_data debe tener la estructura completa según PDF (páginas 7-10).
    Retorna (success, tracking_number, mensaje, status_code)
    """
    try:
        # El body debe incluir los campos: sellerId, trackingNumber (opcional), order
        # Según el PDF, el objeto principal tiene "order" dentro.
        # Asegurarse de que la estructura sea:
        # {
        #   "sellerId": "...",
        #   "trackingNumber": "...", (opcional)
        #   "order": { ... }
        # }
        resp = _request("POST", "orders", email, db, body=orden_data)
        if resp.status_code == 200:
            data = resp.json()
            tn = data.get("trackingNumber") or data.get("order", {}).get("trackingNumber")
            return True, tn, "Orden creada", 200
        else:
            return False, None, f"Error {resp.status_code}: {resp.text}", resp.status_code
    except Exception as e:
        return False, None, str(e), 500

def cancelar_orden(email, db, tracking_number):
    """PATCH /v1/orders/{trackingNumber}/cancel"""
    try:
        resp = _request("PATCH", f"orders/{tracking_number}/cancel", email, db)
        if resp.status_code == 200:
            return True, "Cancelación exitosa", 200
        else:
            return False, f"Error {resp.status_code}: {resp.text}", resp.status_code
    except Exception as e:
        return False, str(e), 500

def obtener_rotulos(email, db, lista_pedidos, label_format=None):
    """
    POST /v1/labels
    lista_pedidos = [ {"sellerId": "...", "trackingNumber": "..."}, ... ]
    Retorna lista de resultados con fileBase64, fileName, result.
    """
    try:
        resp = _request("POST", "labels", email, db, body=lista_pedidos, label_format=label_format)
        if resp.status_code == 200:
            return True, resp.json(), 200
        else:
            return False, f"Error {resp.status_code}: {resp.text}", resp.status_code
    except Exception as e:
        return False, str(e), 500

def consultar_historial(email, db, tracking_numbers, ext_client=None):
    """
    GET /v1/tracking  (según documentación es GET pero con body - inconsistente)
    Como fallback, probamos primero con GET + query params.
    Si da error 400, intentamos POST.
    tracking_numbers: lista de strings.
    ext_client: string de 3 dígitos (opcional)
    """
    params = {}
    if ext_client:
        params["extClient"] = ext_client
    # Intentar GET con query params: ?trackingNumber=...&trackingNumber=...
    # Pero la documentación muestra un array en el body, lo cual no es estándar.
    # Probamos primero con POST (muchas APIs de logística argentinas usan POST para consultas masivas)
    try:
        # Opción 1: POST (más probable que funcione)
        body = [{"trackingNumber": tn} for tn in tracking_numbers]
        resp = _request("POST", "tracking", email, db, body=body, params=params)
        if resp.status_code == 200:
            return True, resp.json(), 200
        # Si da 405 (Method not allowed), probamos GET
        if resp.status_code == 405:
            # Opción 2: GET con query params
            params_list = params.copy()
            for tn in tracking_numbers:
                params_list.setdefault("trackingNumber", []).append(tn)
            resp2 = _request("GET", "tracking", email, db, params=params_list)
            if resp2.status_code == 200:
                return True, resp2.json(), 200
            else:
                return False, f"GET también falló: {resp2.text}", resp2.status_code
        else:
            return False, f"Error {resp.status_code}: {resp.text}", resp.status_code
    except Exception as e:
        return False, str(e), 500

def obtener_sucursales(email, db, state_id=None, pickup_availability=None, package_reception=None):
    """GET /v1/agencies con filtros opcionales."""
    params = {}
    if state_id:
        params["stateId"] = state_id
    if pickup_availability is not None:
        params["pickup_availability"] = str(pickup_availability).lower()
    if package_reception is not None:
        params["package_reception"] = str(package_reception).lower()
    try:
        resp = _request("GET", "agencies", email, db, params=params)
        if resp.status_code == 200:
            return True, resp.json(), 200
        else:
            return False, f"Error {resp.status_code}: {resp.text}", resp.status_code
    except Exception as e:
        return False, str(e), 500
