(function() {
  let sdkCargado = false;

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

  function actualizarStockUI(productosConStock) {
    for (const item of productosConStock) {
      if (window[`stock_por_talle_${item.id_base}`]) {
        if (item.talle) {
          window[`stock_por_talle_${item.id_base}`][item.talle] = item.stock_disponible;
        } else {
          window[`stock_por_talle_${item.id_base}`] = { unico: item.stock_disponible };
        }
      }
      const talleSelect = document.getElementById(`talle_${item.id_base}`);
      if (talleSelect && item.talle) {
        actualizarStockPorTalle(item.id_base, item.talle);
      } else {
        const cantidadInput = document.getElementById(`cantidad_${item.id_base}`);
        const agregarBtn = document.getElementById(`btn_agregar_${item.id_base}`);
        if (cantidadInput) {
          cantidadInput.max = item.stock_disponible;
          if (item.stock_disponible <= 0) {
            cantidadInput.disabled = true;
            cantidadInput.value = 0;
            if (agregarBtn) {
              agregarBtn.disabled = true;
              agregarBtn.textContent = '❌ Sin stock';
            }
          } else {
            cantidadInput.disabled = false;
            if (agregarBtn) {
              agregarBtn.disabled = false;
              agregarBtn.textContent = 'Agregar al carrito';
            }
          }
        }
      }
    }
  }

  async function pagarTodoJunto() {
    console.log("🛒 Iniciando proceso de pago...");

    const carrito = window.carrito || [];
    if (carrito.length === 0) {
      alert("❌ El carrito está vacío");
      return;
    }

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

    const itemsVerificar = carrito.map(item => ({
      id_base: item.id_base,
      talle: item.talle || 'unico',
      cantidad: item.cantidad
    }));

    const btnPagarFinal = document.getElementById('btnPagarFinal');
    if (btnPagarFinal) {
      btnPagarFinal.disabled = true;
      btnPagarFinal.textContent = 'Verificando stock...';
    }

    try {
      const verifyResp = await fetch(`${window.URL_BACKEND}/verificar-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_vendedor: window.cliente.email,
          items: itemsVerificar
        })
      });

      if (!verifyResp.ok) {
        const errorText = await verifyResp.text();
        throw new Error(`Error al verificar stock: ${verifyResp.status} ${errorText}`);
      }

      const verifyData = await verifyResp.json();

      if (!verifyData.ok) {
        let mensaje = "❌ No hay suficiente stock para:\n";
        verifyData.faltantes.forEach(item => {
          mensaje += `- ${item.nombre} (talle: ${item.talle}): disponible ${item.stock_disponible}, solicitado ${item.cantidad_solicitada}\n`;
        });
        alert(mensaje);

        if (verifyData.productos_actualizados) {
          actualizarStockUI(verifyData.productos_actualizados);
        }

        if (btnPagarFinal) {
          btnPagarFinal.disabled = false;
          btnPagarFinal.textContent = 'Pagar con Mercado Pago';
        }
        return;
      }

      btnPagarFinal.textContent = 'Generando pago...';

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
      if (btnPagarFinal) {
        btnPagarFinal.disabled = false;
        btnPagarFinal.textContent = 'Pagar con Mercado Pago';
      }
    }
  }

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

  window.initMercadoPago = initMercadoPago;
  window.pagarTodoJunto = pagarTodoJunto;
})();
