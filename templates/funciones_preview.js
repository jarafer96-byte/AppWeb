function editarPrecio(id) {
  const span = document.getElementById("precio_" + id);
  if (!span) {
    console.warn("❌ No se encontró el span con id:", "precio_" + id);
    return;
  }

  const valorActual = span.textContent.replace("$", "").trim();
  console.log("🧪 Editando precio para:", id, "| Valor actual:", valorActual);

  const input = document.createElement("input");
  input.type = "number";
  input.value = valorActual;
  input.className = "form-control form-control-sm d-inline-block";
  input.style.width = "80px";
  input.id = "input_precio_" + id;  // ✅ ID único para el input

  // ✅ Guardar al salir del input
  input.onblur = () => {
    console.log("📤 onblur: guardando precio para", id, "con valor:", input.value);
    guardarPrecio(id);
  };

  // ✅ Guardar al presionar Enter
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      console.log("⏎ Enter presionado: guardando precio para", id, "con valor:", input.value);
      input.blur(); // dispara onblur
    }
  });

  span.replaceWith(input);
  input.focus();
}
  
function guardarPrecio(id) {
  console.log("🟡 Iniciando guardarPrecio para:", id);

  const input = document.getElementById("input_precio_" + id);
  if (!input) {
    console.warn("❌ No se encontró el input con id:", "input_precio_" + id);
    return;
  }

  const nuevoValor = parseFloat(input.value);
  console.log("🔍 Valor ingresado:", input.value, "| Parseado:", nuevoValor);

  if (isNaN(nuevoValor)) {
    console.warn("⚠️ Valor ingresado no es un número válido:", input.value);
    alert("❌ El precio ingresado no es válido");
    return;
  }

  console.log("🧪 Precio validado para", id, "→", nuevoValor);

  // ✅ Enviar al backend antes de modificar el DOM
  console.log("📡 Enviando fetch a /actualizar-precio con:", { id, nuevoPrecio: nuevoValor });

  fetch('/actualizar-precio', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, nuevoPrecio: nuevoValor })
  })
    .then(res => {
      console.log("📬 Respuesta recibida del backend:", res.status);
      return res.json();
    })
    .then(data => {
      console.log("📨 Payload recibido:", data);
      if (data.status === "ok") {
        console.log("✅ Precio confirmado en Firestore para", id);

        // ✅ Actualizar el DOM solo si el backend responde OK
        const span = document.createElement("span");
        span.id = "precio_" + id;
        span.textContent = "$" + nuevoValor.toFixed(2);
        span.className = input.className;  // hereda estilos del input
        span.classList.add("text-success");  // feedback visual
        input.replaceWith(span);
        setTimeout(() => span.classList.remove("text-success"), 1000);

        if (typeof mostrarAvisoPrecio === "function") {
          console.log("🔔 Ejecutando mostrarAvisoPrecio()");
          mostrarAvisoPrecio();
        }
      } else {
        console.warn("❌ Error en respuesta del backend:", data);
        input.classList.add("is-invalid");
        alert("❌ No se pudo actualizar el precio en el servidor");
      }
    })
    .catch(err => {
      console.error("❌ Error de red al actualizar precio:", err);
      input.classList.add("is-invalid");
      alert("❌ Error de conexión al guardar el precio");
    });
}

function loginAdmin(event) {
  event.preventDefault();
  const usuario = document.getElementById("usuario_login").value.trim();
  const clave = document.getElementById("clave_login").value.trim();

  fetch("/login-admin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, clave })
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === "ok") {
        alert("✅ Acceso concedido");
        location.href = window.location.href;
      } else {
        alert("❌ " + data.message);
      }
    })
    .catch(err => {
      console.error("❌ Error en login:", err);
      alert("❌ Error al intentar login");
    });
}

function editarTalles(id) {
  const selector = document.getElementById("talle_" + id);
  const span = document.getElementById("talles_" + id);

  let tallesActuales = "";

  if (selector) {
    tallesActuales = Array.from(selector.options).map(opt => opt.value).join(", ");
  } else if (span) {
    tallesActuales = span.textContent;
  } else {
    console.warn("❌ No se encontró selector ni span para:", id);
    return;
  }

  const nuevoTalle = prompt("Modificar talles (separados por coma):", tallesActuales);
  if (nuevoTalle === null) return;

  const tallesArray = nuevoTalle.split(',').map(t => t.trim()).filter(t => t);
  console.log("✅ Nuevos talles ingresados:", tallesArray);

  // ✅ Enviar al backend antes de modificar el DOM
  fetch('/actualizar-talles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: id, talles: tallesArray })
  })
    .then(res => res.json())
    .then(data => {
      console.log("📨 Payload recibido:", data);
      if (data.status === "ok") {
        console.log("✅ Talles confirmados en Firestore para", id);

        // ✅ Actualizar visualmente solo si el backend responde OK
        const nuevoSelect = document.createElement("select");
        nuevoSelect.id = "talle_" + id;
        nuevoSelect.className = "form-select form-select-sm w-auto d-inline-block";
        tallesArray.forEach(t => {
          const option = document.createElement("option");
          option.value = t;
          option.textContent = t;
          nuevoSelect.appendChild(option);
        });

        if (selector) {
          selector.replaceWith(nuevoSelect);
        } else if (span) {
          const nuevoSpan = document.createElement("span");
          nuevoSpan.id = "talles_" + id;
          nuevoSpan.textContent = tallesArray.join(', ');
          span.replaceWith(nuevoSpan);
        }

        // ✅ Feedback visual
        nuevoSelect.classList.add("text-success");
        setTimeout(() => nuevoSelect.classList.remove("text-success"), 1000);
      } else {
        console.warn("❌ Error en respuesta del backend:", data);
        alert("❌ No se pudo actualizar los talles");
      }
    })
    .catch(err => {
      console.error("❌ Error en fetch al actualizar talles:", err);
      alert("❌ Error de conexión al guardar los talles");
    });
}
 
function guardarTalles(id) {
  console.log("🟡 Iniciando guardarTalles para:", id);

  const input = document.getElementById("talles_" + id);
  if (!input) {
    console.warn("❌ No se encontró el input con id:", "talles_" + id);
    return;
  }

  const nuevosTalles = input.value
    .split(",")
    .map(t => t.trim())
    .filter(t => t);

  console.log("🧪 Talles capturados para", id, "→", nuevosTalles);

  // ✅ Enviar al backend antes de modificar el DOM
  console.log("📡 Enviando fetch a /actualizar-talles con:", { id_base: id, nuevoTalles: nuevosTalles.join(',') });

  fetch('/actualizar-talles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_base: id, nuevoTalles: nuevosTalles.join(',') })
  })
    .then(res => {
      console.log("📬 Respuesta recibida del backend:", res.status);
      return res.json();
    })
    .then(data => {
      console.log("📨 Payload recibido:", data);
      if (data.status === "ok") {
        console.log("✅ Talles confirmados en Firestore para", id);

        // ✅ Actualizar el DOM solo si el backend responde OK
        const nuevoSpan = document.createElement("span");
        nuevoSpan.id = "talles_" + id;
        nuevoSpan.textContent = nuevosTalles.join(", ");
        nuevoSpan.className = input.className;
        nuevoSpan.classList.add("text-success");
        input.replaceWith(nuevoSpan);
        setTimeout(() => nuevoSpan.classList.remove("text-success"), 1000);
      } else {
        console.warn("❌ Error en respuesta del backend:", data);
        input.classList.add("is-invalid");
        alert("❌ No se pudo actualizar los talles");
      }
    })
    .catch(err => {
      console.error("❌ Error de red al actualizar talles:", err);
      input.classList.add("is-invalid");
      alert("❌ Error de conexión al guardar los talles");
    });
}

function actualizarFirestore(id, datos) {
  if (!id || typeof datos !== "object" || Object.keys(datos).length === 0) {
    console.warn("⚠️ Datos incompletos para actualizar Firestore:", { id, datos });
    return;
  }

  console.log("📡 Enviando actualización a Firestore para", id, "→", datos);

  fetch("/actualizar-firestore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, ...datos })
  })
    .then(res => {
      console.log("📬 Respuesta recibida del backend:", res.status);
      return res.json();
    })
    .then(data => {
      console.log("📨 Payload recibido:", data);
      if (data.status === "ok") {
        console.log("✅ Firestore actualizado para", id);
        if (typeof mostrarAvisoFirestore === "function") {
          console.log("🔔 Ejecutando mostrarAvisoFirestore()");
          mostrarAvisoFirestore();
        }
      } else {
        console.warn("❌ Error en respuesta del backend:", data);
        alert("❌ No se pudo actualizar Firestore");
      }
    })
    .catch(err => {
      console.error("❌ Error de red al actualizar Firestore:", err);
      alert("❌ Error de conexión al guardar los datos");
    });
}

function mostrarAvisoPrecio() {
  const aviso = document.getElementById("avisoPrecio");
  aviso.style.display = "block";
  setTimeout(() => {
    aviso.style.display = "none";
  }, 2000);
}

function pagarConMercadoPago() {
  fetch('/pagar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ carrito })
  })
  .then(res => res.json())
  .then(data => {
    if (data.init_point) {
      window.location.href = data.init_point;
    } else {
      alert("Error al generar pago");
    }
  });
}

function eliminarProducto(id_base, talle, event) {
  event.stopPropagation(); // 👈 evita que el clic cierre el carrito
  carrito = carrito.filter(p => !(p.id_base === id_base && p.talle === talle));
  actualizarCarrito();
}


    function vaciarCarrito() {
      carrito = [];
      actualizarCarrito();
    }
    function actualizarPrecioEnCarrito(nombre, nuevoPrecio) {
  let cambio = false;
  carrito.forEach(item => {
    if (item.nombre === nombre && item.precio !== nuevoPrecio) {
      console.log(`🔄 Actualizando precio en carrito para ${nombre}: ${item.precio} → ${nuevoPrecio}`);
      item.precio = nuevoPrecio;
      cambio = true;
    }
  });
  if (cambio) actualizarCarrito();
}

function sincronizarPreciosDelCarrito() {
  carrito.forEach(item => {
    const idPrecio = "precio_" + (item.id_base || item.nombre.replace(/ /g, "_"));
    const precioSpan = document.getElementById(idPrecio);
    if (precioSpan) {
      const precioActual = parseFloat(precioSpan.textContent.replace("$", ""));
      if (!isNaN(precioActual)) {
        item.precio = precioActual;
      } else {
        console.warn("⚠️ Precio no numérico en DOM para", idPrecio);
      }
    } else {
      console.warn("⚠️ No se encontró el span de precio para", idPrecio);
    }
  });
}
