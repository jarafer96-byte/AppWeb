(function() {
  // Variable interna para evitar cargar el SDK múltiples veces
  let sdkCargado = false;

  // Función auxiliar para cargar el SDK de Mercado Pago
  async function cargarSDK() {
    if (window.MercadoPago) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://sdk.mercadopago.com/js/v2';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  // Inicializa Mercado Pago con la clave pública
  async function initMercadoPago() {
  try {
    await cargarSDK();
    const resp = await fetch(`${window.URL_BACKEND}/api/mp_public_key?email=${encodeURIComponent(window.cliente.email)}`);
    const data = await resp.json();
    if (data.public_key) {
      window.mp = new window.MercadoPago(data.public_key, { locale: 'es-AR' });
      const pagarBtn = document.getElementById('btn_pagar');
      if (pagarBtn) pagarBtn.disabled = false;
    } else {
      const pagarBtn = document.getElementById('btn_pagar');
      if (pagarBtn) pagarBtn.disabled = true;
    }
  } catch {
    const pagarBtn = document.getElementById('btn_pagar');
    if (pagarBtn) pagarBtn.disabled = true;
  }
}

  // Función principal de pago (la que se llama desde el botón "Pagar con Mercado Pago")
  async function pagarTodoJunto() {
    console.log("🛒 Iniciando proceso de pago...");

    const carrito = window.carrito || [];
    if (carrito.length === 0) {
      alert("❌ El carrito está vacío");
      return;
    }

    // Obtener datos del formulario
    const nombreInput = document.querySelector('input[name="nombre"]');
    const apellidoInput = document.querySelector('input[name="apellido"]');
    const emailInput = document.querySelector('input[name="email"]');
    const telefonoInput = document.querySelector('input[name="telefono"]');

    if (!nombreInput || !apellidoInput || !emailInput) {
      alert("❌ Por favor completa todos los campos obligatorios");
      return;
    }

    const nombre = nombreInput.value.trim();
    const apellido = apellidoInput.value.trim();
    const emailCliente = emailInput.value.trim();
    const telefono = telefonoInput?.value?.trim() || "";

    if (!nombre || !apellido || !emailCliente) {
      alert("❌ Nombre, apellido y email son obligatorios");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(emailCliente)) {
      alert("❌ Por favor ingresa un email válido");
      return;
    }

    // Preparar items
    function convertirPrecio(precio) {
      if (typeof precio === 'number') return precio;
      if (typeof precio === 'string') {
        const limpio = precio.replace(/[$\s,]/g, '').trim();
        const num = parseFloat(limpio);
        return isNaN(num) ? 0 : num;
      }
      return 0;
    }

    function convertirCantidad(cantidad) {
      const num = parseInt(cantidad);
      return isNaN(num) || num < 1 ? 1 : num;
    }

    const itemsMP = [];
    const itemsCarrito = [];
    let totalCalculado = 0;

    carrito.forEach(item => {
      const precio = convertirPrecio(item.precio);
      const cantidad = convertirCantidad(item.cantidad);
      const subtotal = precio * cantidad;
      totalCalculado += subtotal;

      itemsMP.push({
        title: item.nombre + (item.talle ? ` (${item.talle})` : ""),
        quantity: cantidad,
        unit_price: precio,
        currency_id: "ARS"
      });

      itemsCarrito.push({
        nombre: item.nombre,
        precio: precio,
        cantidad: cantidad,
        talle: item.talle || "",
        id_base: item.id_base || "",
        grupo: item.grupo || "",
        subgrupo: item.subgrupo || "",
        subtotal: subtotal
      });
    });

    const orden_id = 'ORD_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    const payload = {
      email_vendedor: window.cliente.email,
      carrito: itemsCarrito,
      items_mp: itemsMP,
      total: totalCalculado,
      cliente_nombre: `${nombre} ${apellido}`.trim(),
      cliente_email: emailCliente,
      cliente_telefono: telefono,
      orden_id: orden_id,
      url_retorno: window.location.href
    };

    try {
      const btnPagarFinal = document.getElementById('btnPagarFinal');
      if (btnPagarFinal) {
        btnPagarFinal.disabled = true;
        btnPagarFinal.textContent = 'Procesando...';
      }

      // Asegurar que el SDK esté cargado
      await cargarSDK();

      const response = await fetch(`${window.URL_BACKEND}/pagar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Error HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();

      if (data.error) {
        alert("❌ Error: " + data.error);
      } else if (data.init_point) {
        localStorage.setItem('ultima_orden_id', orden_id);
        localStorage.setItem('ultima_orden_data', JSON.stringify({
          fecha: new Date().toISOString(),
          items: carrito.length,
          total: totalCalculado,
          cliente: `${nombre} ${apellido}`,
          email: emailCliente
        }));
        window.location.href = data.init_point;
      } else if (data.preference_id && window.mp) {
        localStorage.setItem('ultima_orden_id', orden_id);
        window.mp.checkout({
          preference: { id: data.preference_id },
          autoOpen: true
        });
      } else {
        console.warn("Respuesta inesperada:", data);
        alert("⚠️ No se pudo procesar el pago. Intenta de nuevo.");
      }
    } catch (error) {
      console.error("💥 Error al procesar el pago:", error);
      alert("❌ Error al procesar el pago: " + error.message);
    } finally {
      const btnPagarFinal = document.getElementById('btnPagarFinal');
      if (btnPagarFinal) {
        btnPagarFinal.disabled = false;
        btnPagarFinal.textContent = 'Pagar con Mercado Pago';
      }
    }
  }

  // Verificación de configuración de Mercado Pago (parámetros en URL)
  setTimeout(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mp_configurado') === 'true') {
      alert('✅ ¡Mercado Pago configurado exitosamente! Ahora puedes recibir pagos.');
      const nuevaURL = window.location.pathname + '?email=' + encodeURIComponent(urlParams.get('email'));
      window.history.replaceState({}, document.title, nuevaURL);
      setTimeout(() => location.reload(), 1500);
    }
    if (urlParams.get('mp_error') === '1') {
      alert('❌ Hubo un error al configurar Mercado Pago. Por favor, intenta nuevamente.');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, 100);

  // Exponer solo las funciones necesarias
  window.initMercadoPago = initMercadoPago;
  window.pagarTodoJunto = pagarTodoJunto;
})();