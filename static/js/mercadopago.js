(function() {
  let costoEnvio = 0;

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

  function resetEnvio() {
    costoEnvio = 0;
    window.costoEnvio = 0;               // Sincronizar variable global
    const divCosto = document.getElementById('costoEnvioMostrado');
    if (divCosto) divCosto.innerHTML = '';
  }
  window.resetEnvio = resetEnvio;

  async function initMercadoPago() {
    try {
      await cargarSDK();
      const resp = await fetch(`/api/mp_public_key?email=${encodeURIComponent(window.cliente.email)}`);
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

  async function calcularEnvio() {
    const emailVendedor = window.cliente?.email;
    if (!emailVendedor) {
      alert("No se pudo identificar al vendedor");
      return;
    }

    const codigoPostal = document.getElementById('codigo_postal')?.value.trim();
    if (!codigoPostal) {
      alert("Ingresá tu código postal para calcular el envío");
      return;
    }

    let pesoTotalKg = 0;
    for (const item of window.carrito) {
      const producto = window.todosLosProductos?.find(p => p.id_base === item.id_base);
      const pesoGramos = producto?.peso_gramos || 500;
      pesoTotalKg += (pesoGramos * item.cantidad) / 1000;
    }

    const altoCm = 10, anchoCm = 15, largoCm = 20;
    const payload = {
      email_vendedor: emailVendedor,
      codigo_postal_destino: codigoPostal,
      peso_kg: pesoTotalKg,
      alto_cm: altoCm,
      ancho_cm: anchoCm,
      largo_cm: largoCm
    };

    const btnCalcular = document.getElementById('btnCalcularEnvio');
    if (btnCalcular) {
      btnCalcular.disabled = true;
      btnCalcular.textContent = 'Calculando...';
    }

    try {
      const resp = await fetch("/ca/cotizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (data.ok && data.costo) {
        costoEnvio = data.costo;
        window.costoEnvio = costoEnvio;
        const divCosto = document.getElementById("costoEnvioMostrado");
        if (divCosto) divCosto.innerHTML = `<strong>Envío:</strong> $${costoEnvio.toFixed(2)}`;
        actualizarCarritoConEnvio();
      } else {
        alert("No se pudo calcular el envío: " + (data.error || "Error desconocido"));
        costoEnvio = 0;
        window.costoEnvio = 0;
        const divCosto = document.getElementById("costoEnvioMostrado");
        if (divCosto) divCosto.innerHTML = "";
      }
    } catch (err) {
      console.error(err);
      alert("Error al calcular envío. Verifica tu conexión.");
      costoEnvio = 0;
      window.costoEnvio = 0;
    } finally {
      if (btnCalcular) {
        btnCalcular.disabled = false;
        btnCalcular.textContent = 'Calcular envío';
      }
    }
  }

  function actualizarCarritoConEnvio() {
    let subtotal = 0;
    if (window.carrito && window.carrito.length) {
      subtotal = window.carrito.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
    }
    const envio = (typeof window.costoEnvio !== 'undefined') ? window.costoEnvio : costoEnvio;
    let total = subtotal + envio;
    const totalSpan = document.getElementById('totalCarrito');
    if (totalSpan) totalSpan.textContent = total.toFixed(2);
    let envioLinea = document.getElementById('envioLinea');
    if (!envioLinea && window.carrito.length) {
      const lista = document.getElementById('listaCarrito');
      if (lista) {
        envioLinea = document.createElement('li');
        envioLinea.id = 'envioLinea';
        envioLinea.style.listStyle = 'none';
        envioLinea.style.marginTop = '8px';
        envioLinea.style.borderTop = '1px solid #ccc';
        lista.appendChild(envioLinea);
      }
    }
    if (envioLinea) {
      envioLinea.innerHTML = `<div style="display:flex; justify-content:space-between;">
        <span>Envío</span>
        <span>$${envio.toFixed(2)}</span>
      </div>`;
    }
  }
  window.actualizarCarritoConEnvio = actualizarCarritoConEnvio;

  async function pagarTodoJunto() {
    const carrito = window.carrito || [];
    if (carrito.length === 0) {
      alert("❌ El carrito está vacío");
      return;
    }

    // Campos obligatorios siempre
    const nombreInput = document.getElementById('nombre');
    const apellidoInput = document.getElementById('apellido');
    const emailInput = document.getElementById('email_cliente');
    const telefonoInput = document.getElementById('telefono');

    if (!nombreInput || !apellidoInput || !emailInput) {
      alert("❌ Por favor completa nombre, apellido y email");
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

    // Determinar si hay envío (costo > 0)
    const tieneEnvio = (window.costoEnvio || costoEnvio) > 0;

    let calle = "", numero = "", localidad = "", provinciaCodigo = "", codigoPostal = "";

    if (tieneEnvio) {
      const calleInput = document.getElementById('calle');
      const numeroInput = document.getElementById('numero');
      const localidadInput = document.getElementById('localidad');
      const provinciaSelect = document.getElementById('provincia_codigo');
      const codigoPostalInput = document.getElementById('codigo_postal');

      if (!calleInput || !numeroInput || !localidadInput || !provinciaSelect || !codigoPostalInput) {
        alert("❌ Error: faltan campos de dirección en el formulario");
        return;
      }

      calle = calleInput.value.trim();
      numero = numeroInput.value.trim();
      localidad = localidadInput.value.trim();
      provinciaCodigo = provinciaSelect.value;
      codigoPostal = codigoPostalInput.value.trim();

      if (!calle || !numero || !localidad || !provinciaCodigo || !codigoPostal) {
        alert("❌ Para el envío, todos los campos de dirección son obligatorios");
        return;
      }
    }

    // Si no hay envío, aún podemos permitir que el usuario haya ingresado dirección, pero no la usamos.
    // Para el payload, si no hay envío, enviamos un objeto vacío o null.
    const clienteDireccion = tieneEnvio ? {
      calle,
      numero,
      localidad,
      provincia_codigo: provinciaCodigo,
      codigo_postal: codigoPostal
    } : {};

    const itemsVerificar = carrito.filter(item => item.id_base).map(item => ({
      id_base: item.id_base,
      talle: item.talle || 'unico',
      cantidad: item.cantidad
    }));

    if (itemsVerificar.length === 0) {
      alert("❌ El carrito no contiene productos válidos para procesar el pago.");
      if (btnPagarFinal) {
        btnPagarFinal.disabled = false;
        btnPagarFinal.textContent = 'Pagar con Mercado Pago';
      }
      return;
    }

    const btnPagarFinal = document.getElementById('btnPagarFinal');
    if (btnPagarFinal) {
      btnPagarFinal.disabled = true;
      btnPagarFinal.textContent = 'Verificando stock...';
    }

    try {
      const verifyResp = await fetch(`/verificar-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_vendedor: window.cliente.email,
          carrito: itemsVerificar 
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
      let subtotalProductos = 0;

      carrito.forEach(item => {
        const precio = convertirPrecio(item.precio);
        const cantidad = convertirCantidad(item.cantidad);
        const subtotal = precio * cantidad;
        subtotalProductos += subtotal;

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

      const totalFinal = subtotalProductos + (window.costoEnvio || costoEnvio);
      const orden_id = 'ORD_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

      const payload = {
        email_vendedor: window.cliente.email,
        carrito: itemsCarrito,
        items_mp: itemsMP,
        total: totalFinal,
        costo_envio: window.costoEnvio || costoEnvio,
        cliente_nombre: `${nombre} ${apellido}`.trim(),
        cliente_email: emailCliente,
        cliente_telefono: telefono,
        cliente_direccion: clienteDireccion,
        orden_id: orden_id,
        url_retorno: window.location.href
      };

      await cargarSDK();

      const response = await fetch(`/pagar`, {
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
          total: totalFinal,
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
        alert("⚠️ No se pudo procesar el pago. Intenta de nuevo.");
      }
    } catch (error) {
      alert("❌ Error al procesar el pago: " + error.message);
    } finally {
      if (btnPagarFinal) {
        btnPagarFinal.disabled = false;
        btnPagarFinal.textContent = 'Pagar con Mercado Pago';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btnCalcular = document.getElementById('btnCalcularEnvio');
    if (btnCalcular) {
      btnCalcular.addEventListener('click', calcularEnvio);
    }
  });

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
  window.calcularEnvio = calcularEnvio;
})();
