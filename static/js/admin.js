window.todosLosProductos = window.todosLosProductos || [];

async function guardarProducto(producto, formDiv, skipReload = false) {
  const email = window.cliente?.email;
  if (!email) {
    alert("❌ No hay email de admin, no se puede guardar");
    return false;
  }

  let idBase = formDiv?.dataset?.idBase;
  let esEdicion = !!idBase && !idBase.startsWith('nuevo_');

  if (idBase && idBase.startsWith('nuevo_')) {
    delete producto.id_base;
    idBase = null;
  }

  const payload = {
    producto: producto,
    email: email,
    es_edicion: esEdicion
  };
  if (esEdicion) {
    payload.producto.id_base = idBase;
  }

  try {
    const resp = await fetch("/guardar-producto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Error HTTP ${resp.status}: ${text.substring(0, 200)}`);
    }
    const data = await resp.json();
    if (data.status === "ok") {
      if (typeof mostrarToast === 'function') {
        mostrarToast(`✅ ${producto.nombre} guardado`);
      }
      if (!skipReload) {
        await recargarProductos();
        renderTablaProductos();
      }
      return true;
    } else {
      throw new Error(data.error || data.message || "Error al guardar producto");
    }
  } catch (err) {
    alert("❌ Error: " + err.message);
    return false;
  }
}

function abrirConfigCorreoArgentino() {
  const modal = document.getElementById('modalConfigCA');
  if (modal) {
    modal.style.display = 'flex';
  }
}

function cerrarModalConfigCA() {
  const modal = document.getElementById('modalConfigCA');
  if (modal) {
    modal.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('formConfigCA');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const email = window.cliente?.email;
      if (!email) {
        alert("No se detectó el email del vendedor. Inicia sesión nuevamente.");
        return;
      }

      const agreement = document.getElementById('ca_agreement').value.trim();
      const api_key = document.getElementById('ca_api_key').value.trim();
      const micorreo_user = document.getElementById('ca_micorreo_user').value.trim();
      const micorreo_password = document.getElementById('ca_micorreo_password').value.trim();
      const test_mode = document.getElementById('ca_test_mode').checked;
      
      const nombre = document.getElementById('ca_nombre').value.trim();
      const calle = document.getElementById('ca_calle').value.trim();
      const altura = document.getElementById('ca_altura').value.trim();
      const localidad = document.getElementById('ca_localidad').value.trim();
      const provincia_codigo = document.getElementById('ca_provincia_codigo').value.trim();
      const codigo_postal = document.getElementById('ca_codigo_postal').value.trim();
      
      if (!agreement || !api_key || !micorreo_user || !micorreo_password ||
          !nombre || !calle || !altura || !localidad || !provincia_codigo || !codigo_postal) {
        alert("Por favor completa todos los campos.");
        return;
      }

      const submitBtn = form.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerText;
      submitBtn.innerText = "Guardando...";
      submitBtn.disabled = true;
      
      try {
        const credRes = await fetch("/ca/guardar-credenciales", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agreement, api_key, micorreo_user, micorreo_password, test_mode })
        });
        const credData = await credRes.json();
        if (credData.status !== "ok") throw new Error(credData.error || "Error guardando credenciales");

        const remRes = await fetch("/ca/guardar-remitente", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nombre, calle, altura, localidad, provincia_codigo, codigo_postal })
        });
        const remData = await remRes.json();
        if (remData.status !== "ok") throw new Error(remData.error || "Error guardando remitente");
        
        alert("✅ Configuración de Correo Argentino guardada correctamente.");
        cerrarModalConfigCA();

        form.reset();
      } catch (err) {
        alert("❌ Error: " + err.message);
      } finally {
        submitBtn.innerText = originalText;
        submitBtn.disabled = false;
      }
    });
  }
});

async function eliminarProducto(id_base) {
  if (id_base && id_base.startsWith('nuevo_')) {
    const index = window.todosLosProductos.findIndex(p => p.id_base === id_base);
    if (index !== -1) {
      window.todosLosProductos.splice(index, 1);
      const grupoActivo = document.querySelector('.grupo-btn.active');
      const grupo = grupoActivo ? grupoActivo.dataset.grupo : null;
      const subgrupoActivo = document.querySelector('.subgrupo-btn.active');
      const subgrupo = subgrupoActivo ? subgrupoActivo.dataset.subgrupo : null;
      if (grupo) {
        filtrarProductos(grupo, subgrupo);
      } else {
        renderTablaProductos();
      }
      if (typeof mostrarToast === 'function') mostrarToast('✅ Producto eliminado (sin guardar)');
    }
    return;
  }

  try {
    const resp = await fetch("/eliminar-producto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_base, email: window.cliente.email })
    });
    const data = await resp.json();
    if (data.status === "ok") {
      await recargarProductos();
      renderTablaProductos();
      if (typeof mostrarToast === 'function') mostrarToast('✅ Producto eliminado');
    } else {
      alert("Error al eliminar producto: " + (data.error || data.message || "Error desconocido"));
    }
  } catch (err) {
    alert("Error al eliminar producto: " + err.message);
  }
}


async function optimizarImagen(file) {
  const imgUrl = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = imgUrl;
    });
    const targetW = 500, targetH = 500;
    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d", { alpha: true });
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.clearRect(0, 0, targetW, targetH);
    const ratio = Math.min(targetW / img.width, targetH / img.height);
    const newW = Math.max(1, Math.round(img.width * ratio));
    const newH = Math.max(1, Math.round(img.height * ratio));
    const offsetX = Math.floor((targetW - newW) / 2);
    const offsetY = Math.floor((targetH - newH) / 2);
    ctx.drawImage(img, offsetX, offsetY, newW, newH);
    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(b => {
        if (b && b.size > 0) resolve(b);
        else reject(new Error("❌ No se pudo generar WebP"));
      }, "image/webp", 0.8);
    });
    return blob;
  } finally {
    URL.revokeObjectURL(imgUrl);
  }
}


async function subirImagen(blob) {
  const formData = new FormData();
  formData.append('file', blob, 'imagen.webp');
  formData.append('email', window.cliente.email);
  const resp = await fetch('/subir-foto', {
    method: 'POST',
    body: formData
  });
  const data = await resp.json();
  if (data.ok && data.url) return data.url;
  throw new Error('Error al subir imagen');
}


function duplicarProductoDesdeCard(id_base) {
  const original = window.todosLosProductos?.find(p => p.id_base === id_base);
  if (!original) {
    alert("❌ Producto no encontrado");
    return;
  }

  const copia = JSON.parse(JSON.stringify(original));

  delete copia.id_base;
  copia.id_base = 'nuevo_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

  copia.imagen_url = '';
  copia.fotos_adicionales = [];

  window.todosLosProductos.push(copia);

  const grupoActivo = document.querySelector('.grupo-btn.active');
  const grupo = grupoActivo ? grupoActivo.dataset.grupo : null;
  const subgrupoActivo = document.querySelector('.subgrupo-btn.active');
  const subgrupo = subgrupoActivo ? subgrupoActivo.dataset.subgrupo : null;

  if (grupo) {
    filtrarProductos(grupo, subgrupo);
  } else {
    renderTablaProductos();
  }

  setTimeout(() => {
    const nuevaFila = document.querySelector(`tr[data-id-base="${copia.id_base}"]`);
    if (nuevaFila) {
      nuevaFila.scrollIntoView({ behavior: 'smooth', block: 'center' });
      nuevaFila.classList.add('table-active');
      setTimeout(() => nuevaFila.classList.remove('table-active'), 2000);
    }
  }, 100);
}


function abrirConfigMercadoPago() {
  const urlRetorno = window.location.href;
  const configUrl = `/conectar_mp?email=${encodeURIComponent(window.cliente.email)}&url_retorno=${encodeURIComponent(urlRetorno)}&token=${encodeURIComponent(window.tokenAdmin)}`;
  window.location.href = configUrl;
}


function salirAdmin() {
  window.modoAdmin = false;
  window.tokenAdmin = null;
  history.replaceState(null, "", window.location.pathname);

  const adminContainer = document.getElementById('adminFormsContainer');
  if (adminContainer) adminContainer.classList.add('d-none');

  const formsList = document.getElementById('formsList');
  if (formsList) formsList.style.display = 'block'; 

  const logoutWrapper = document.getElementById('logoutAdminWrapper');
  if (logoutWrapper) logoutWrapper.style.display = 'none';

  const configurarMP = document.getElementById('configurarMP');
  if (configurarMP) configurarMP.classList.add('d-none');

  const configurarCA = document.getElementById('configurarCA');
  if (configurarCA) configurarCA.classList.add('d-none');

  const loginToggleBtn = document.getElementById('loginToggleBtn');
  if (loginToggleBtn) loginToggleBtn.style.display = 'block';

  if (window.currentGrupo) {
    const btnGrupo = Array.from(document.querySelectorAll('.btn-grupo'))
      .find(b => b.textContent.trim().toLowerCase() === window.currentGrupo.toLowerCase());
    if (btnGrupo) {
      mostrarGrupo(window.currentGrupo, { target: btnGrupo });
      if (window.currentSub) {
        setTimeout(() => {
          const btnSub = Array.from(document.querySelectorAll('.btn-subgrupo'))
            .find(b => b.textContent.trim().toLowerCase() === window.currentSub.toLowerCase());
          if (btnSub) mostrarSubgrupo(window.currentSub, { target: btnSub });
          else {
            const subgrupos = [...new Set(window.todosLosProductos
              .filter(p => p.grupo?.toLowerCase() === window.currentGrupo.toLowerCase())
              .map(p => p.subgrupo).filter(Boolean))];
            if (subgrupos.length > 0) filtrarSubcategoria(window.currentGrupo, subgrupos[0]);
          }
        }, 100);
      }
    } else {
      const primerGrupo = document.querySelector('.btn-grupo');
      if (primerGrupo) mostrarGrupo(primerGrupo.textContent.trim(), { target: primerGrupo });
    }
  } else {
    const primerGrupo = document.querySelector('.btn-grupo');
    if (primerGrupo) mostrarGrupo(primerGrupo.textContent.trim(), { target: primerGrupo });
  }
  location.reload();
}

function loginAdmin(event) {
  event.preventDefault();
  const usuario = document.getElementById("usuario_login").value.trim();
  const clave = document.getElementById("clave_login").value.trim();

  if (!usuario || !clave) {
    alert("❌ Usuario y clave requeridos");
    return;
  }

  const btn = event.target.querySelector('button[type="submit"]');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Entrando...';
  }

  fetch("/login-admin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, clave })
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === "ok" && data.token) {
        alert("✅ Acceso concedido");
        const loginToggleBtn = document.getElementById("loginToggleBtn");
        if (loginToggleBtn) loginToggleBtn.style.display = "none";
        const loginForm = document.getElementById("loginFloatingForm");
        if (loginForm) loginForm.style.display = "none";
        window.location.search = `?token=${data.token}`;
      } else {
        alert("❌ " + data.message);
      }
    })
    .catch(() => {
      alert("❌ Error al intentar login");
    })
    .finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Entrar';
      }
    });
}


async function agregarFotoExtra(btn) {
  const idBase = btn.dataset.id;
  const inputFile = document.createElement('input');
  inputFile.type = 'file';
  inputFile.accept = 'image/*';
  inputFile.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const blob = await optimizarImagen(file);
      const url = await subirImagen(blob);

      const producto = window.todosLosProductos.find(p => p.id_base === idBase);
      if (!producto) return;
      if (!producto.fotos_adicionales) producto.fotos_adicionales = [];
      producto.fotos_adicionales.push(url);

      const contenedor = btn.closest('.fotos-extra-container');
      const listaFotos = contenedor.querySelector('.fotos-extra-list');
      const nuevaFoto = document.createElement('div');
      nuevaFoto.className = 'foto-extra-item d-flex align-items-center justify-content-between mb-1 p-1 border rounded';
      nuevaFoto.innerHTML = `
        <img src="${getVersionUrl(url, '58')}" style="width:40px; height:40px; object-fit:cover; border-radius:4px; cursor:pointer;" onclick="openModal('${url}')">
        <button class="btn btn-sm btn-outline-danger eliminar-foto-extra" data-url="${url}" data-id="${idBase}" style="padding: 2px 8px;">✖</button>
      `;
      listaFotos.appendChild(nuevaFoto);

      if (typeof mostrarToast === 'function') mostrarToast('✅ Foto adicional agregada');
    } catch (err) {
      alert('Error al subir imagen: ' + err.message);
    }
  };
  inputFile.click();
}


async function eliminarFotoExtra(idBase, url) {
  const producto = window.todosLosProductos.find(p => p.id_base === idBase);
  if (producto && producto.fotos_adicionales) {
    const index = producto.fotos_adicionales.indexOf(url);
    if (index !== -1) {
      producto.fotos_adicionales.splice(index, 1);
    }
  }

  const fotoDiv = document.querySelector(`.fotos-extra-container[data-id="${idBase}"] [data-url="${url}"]`)?.closest('div');
  if (fotoDiv) fotoDiv.remove();

  if (typeof mostrarToast === 'function') mostrarToast('✅ Foto extra eliminada');
}


async function agregarImagenPrincipal(btn) {
  const idBase = btn.dataset.id;
  const fila = btn.closest('tr');
  if (!fila) return;

  const inputFile = document.createElement('input');
  inputFile.type = 'file';
  inputFile.accept = 'image/*';
  inputFile.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const blob = await optimizarImagen(file);
      const url = await subirImagen(blob);

      const producto = window.todosLosProductos.find(p => p.id_base === idBase);
      if (producto) {
        producto.imagen_url = url;
      }

      const img = fila.querySelector('td:first-child img');
      if (img) {
        img.src = getVersionUrl(url, '58');
        img.onclick = () => openModal(url);
      }

      if (typeof mostrarToast === 'function') mostrarToast('✅ Imagen principal actualizada');
    } catch (err) {
      alert('Error al subir imagen: ' + err.message);
    }
  };
  inputFile.click();
}


function parsearTallesStock(cadena) {
  const result = {};
  if (!cadena) return result;
  const pares = cadena.split(',').map(s => s.trim());
  pares.forEach(par => {
    const [talle, stock] = par.split(':').map(s => s.trim());
    if (talle && stock !== undefined) {
      const stockNum = parseInt(stock, 10);
      if (!isNaN(stockNum)) {
        result[talle] = stockNum;
      }
    }
  });
  return result;
}


function agregarFilaColor(btn) {
  const contenedor = btn.closest('.colores-stock-container');
  const nuevaFila = document.createElement('div');
  nuevaFila.className = 'fila-color d-flex align-items-center mb-1';
  nuevaFila.style.gap = '5px';
  nuevaFila.innerHTML = `
    <input type="text" class="form-control form-control-sm color-input" placeholder="Color" style="width: 100px;">
    <input type="checkbox" class="talle-toggle" style="margin: 0 5px;">
    <span class="small">Talles</span>
    <input type="number" class="form-control form-control-sm stock-input" placeholder="Stock" style="flex: 1;">
    <button class="btn btn-sm btn-outline-danger eliminar-color" title="Eliminar color">✖</button>
  `;
  
  // Insertar antes del botón "Agregar color"
  contenedor.insertBefore(nuevaFila, btn);
  
  // Asignar evento al botón eliminar
  const eliminarBtn = nuevaFila.querySelector('.eliminar-color');
  eliminarBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    nuevaFila.remove();
  });
  
  // Asignar evento al checkbox para cambiar el tipo de input
  const toggle = nuevaFila.querySelector('.talle-toggle');
  const input = nuevaFila.querySelector('.stock-input'); // inicialmente es number
  toggle.addEventListener('change', function(e) {
    const estaMarcado = this.checked;
    if (estaMarcado) {
      // Cambiar a modo talles (texto)
      const valorActual = input.value;
      input.type = 'text';
      input.classList.remove('stock-input');
      input.classList.add('talles-input');
      input.placeholder = 'S:30, M:20';
      input.value = valorActual; // conservar el valor si era un número
    } else {
      // Cambiar a modo stock único (number)
      let valorActual = input.value;
      let stock = 0;
      if (input.type === 'text') {
        // Si estaba en modo talles, intentar extraer stock total o dejar 0
        const tallesObj = parsearTallesStock(valorActual);
        stock = Object.values(tallesObj).reduce((a, b) => a + b, 0);
      } else {
        stock = parseInt(valorActual, 10) || 0;
      }
      input.type = 'number';
      input.classList.remove('talles-input');
      input.classList.add('stock-input');
      input.placeholder = 'Stock';
      input.value = stock;
    }
  });
}


function renderTablaProductos() {
  const container = document.getElementById('tableView');
  if (!container) return;

  const productos = window.todosLosProductos || [];

  let html = `
    <div class="row">
      <div class="col-12">
        <div class="admin-grupos-bar" style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; align-items: center; overflow-x: auto; padding-bottom: 5px;">
          <button id="adminBtnNuevoGrupo" class="btn btn-sm btn-success">+ Nuevo grupo</button>
          ${renderGruposHorizontal(productos)}
        </div>
        <div id="adminSubgruposBar" class="admin-subgrupos-bar" style="display: none; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; overflow-x: auto; padding-bottom: 5px;"></div>
      </div>
      <div class="col-12">
        <div class="d-flex justify-content-between mb-2">
          <div>
            <button id="btnNuevoProductoTabla" class="btn btn-sm btn-success">➕ Nuevo producto</button>
            <button id="guardarTodosTablaBtn" class="btn btn-sm btn-primary">💾 Guardar todos</button>
          </div>
        </div>
        <div style="overflow-x: auto;">
          <table class="table table-striped table-hover" style="min-width: 800px;">
            <thead>
              <tr>
                <th style="width: 60px;">Imagen</th>
                <th style="width: 80px;">Fotos extra</th>
                <th style="width: 200px;">Producto</th>
                <th style="width: 80px;">Precio</th>
                <th style="width: 80px;">Precio anterior</th> 
                <th style="min-width: 300px;">Colores / Talles / Stock</th>
                <th style="min-width: 200px;">Descripción</th>
                <th style="width: 120px;">Acciones</th>
              </tr>
            </thead>
            <tbody id="tabla-productos-body">
              ${renderFilasTabla(productos)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = html;
}


function renderGruposHorizontal(productos) {
  const grupos = [...new Set(productos.map(p => p.grupo).filter(Boolean))];
  const subgruposPorGrupo = {};
  productos.forEach(p => {
    if (p.grupo && p.subgrupo) {
      if (!subgruposPorGrupo[p.grupo]) subgruposPorGrupo[p.grupo] = new Set();
      subgruposPorGrupo[p.grupo].add(p.subgrupo);
    }
  });

  let html = '';
  grupos.forEach(grupo => {
    const tieneSub = subgruposPorGrupo[grupo] && subgruposPorGrupo[grupo].size > 0;
    html += `
      <div class="admin-grupo-item" data-grupo="${grupo}" style="display: inline-flex; align-items: center;">
        <button class="btn btn-outline-secondary btn-sm grupo-btn" data-grupo="${grupo}">
          ${grupo}
        </button>
        ${tieneSub ? `<button class="btn btn-sm btn-link subgrupo-toggle-btn" data-grupo="${grupo}" style="padding: 0 5px;">▼</button>` : ''}
      </div>
    `;
  });
  return html;
}


function renderFilasTabla(productos) {
  return productos.map(p => {
    const idBase = p.id_base || '';
    const nombre = p.nombre || '';
    const precio = p.precio || 0;
    const precioAnterior = p.precio_anterior || 0;  
    const descripcion = p.descripcion || '';

    const imagenMiniatura = getVersionUrl(p.imagen_url || '/static/img/fallback.webp', '58');

    const imagenPrincipalHTML = `
      <div style="display: flex; flex-direction: column; align-items: center; gap: 6px;">
        <button class="btn btn-sm btn-outline-secondary agregar-imagen-principal w-100" data-id="${idBase}" title="Cambiar imagen principal">
          + 
        </button>
        <img src="${imagenMiniatura}" style="width:58px; height:58px; object-fit:cover; border-radius:4px; cursor:pointer;" onclick="openModal('${p.imagen_url || ''}')">
      </div>
    `;
    let fotosExtraHTML = '';
    fotosExtraHTML += `
      <div class="fotos-extra-header">
        <button class="btn btn-sm btn-outline-secondary agregar-foto-extra w-100" data-id="${idBase}">
          + 
        </button>
      </div>
    `;

    fotosExtraHTML += `<div class="fotos-extra-list" data-id="${idBase}">`;

    if (p.fotos_adicionales && p.fotos_adicionales.length) {
       p.fotos_adicionales.forEach(url => {
        fotosExtraHTML += `
          <div class="foto-extra-item d-flex align-items-center justify-content-between mb-1 p-1 border rounded">
            <img src="${getVersionUrl(url, '58')}" style="width:58px; height:58px; object-fit:cover; border-radius:4px; cursor:pointer;" onclick="openModal('${url}')">
            <button class="btn btn-sm btn-outline-danger eliminar-foto-extra" data-url="${url}" data-id="${idBase}">✖</button>
          </div>
        `;
      });
    }
    fotosExtraHTML += `</div>`;

    let filasColoresHTML = '';
    const variantes = p.variantes || {};
    const porColor = {};
    Object.values(variantes).forEach(v => {
      const color = v.color;
      if (!porColor[color]) porColor[color] = {};
      porColor[color][v.talle] = v.stock;
    });

    if (Object.keys(porColor).length > 0) {
      Object.entries(porColor).forEach(([color, tallesObj]) => {
        const tieneTalles = Object.keys(tallesObj).some(t => t !== 'unico');
        const tallesStr = tieneTalles ? Object.entries(tallesObj)
          .filter(([t]) => t !== 'unico')
          .map(([t, s]) => `${t}:${s}`).join(', ') : '';
        const stockUnico = !tieneTalles ? (tallesObj['unico'] || 0) : 0;

        filasColoresHTML += `
          <div class="fila-color d-flex align-items-center mb-1" style="gap: 5px;">
            <input type="text" class="form-control form-control-sm color-input" value="${color.replace(/"/g, '&quot;')}" placeholder="Color" style="width: 100px;">
            <input type="checkbox" class="talle-toggle" ${tieneTalles ? 'checked' : ''} style="margin: 0 5px;">
            <span class="small">Talles</span>
            <input type="${tieneTalles ? 'text' : 'number'}" class="form-control form-control-sm ${tieneTalles ? 'talles-input' : 'stock-input'}" 
                   value="${tieneTalles ? tallesStr.replace(/"/g, '&quot;') : stockUnico}" 
                   placeholder="${tieneTalles ? 'S:30, M:20' : 'Stock'}" style="flex: 1;">
            <button class="btn btn-sm btn-outline-danger eliminar-fila-color" title="Eliminar color" style="color: red;">✖</button>
          </div>
        `;
      });
    } else {
      filasColoresHTML = `
        <div class="fila-color d-flex align-items-center mb-1" style="gap: 5px;">
          <input type="text" class="form-control form-control-sm color-input" placeholder="Color" style="width: 100px;">
          <input type="checkbox" class="talle-toggle" style="margin: 0 5px;">
          <span class="small">Talles</span>
          <input type="number" class="form-control form-control-sm stock-input" placeholder="Stock" style="flex: 1;">
          <button class="btn btn-sm btn-outline-danger eliminar-color" title="Eliminar color">✖</button>
        </div>
      `;
    }

    const agregarColorBtn = `<button class="btn btn-sm btn-outline-success agregar-fila-color mt-1" data-id="${idBase}" style="color: white;">➕ Agregar color</button>`;

    const coloresCellHTML = `
      <div class="colores-stock-container" data-id="${idBase}">
        ${filasColoresHTML}
        ${agregarColorBtn}
      </div>
    `;

    const descripcionHTML = `<textarea class="form-control form-control-sm descripcion-textarea" rows="2" data-id="${idBase}">${descripcion.replace(/"/g, '&quot;')}</textarea>`;

    return `
      <tr data-id-base="${idBase}">
         <td>${imagenPrincipalHTML}</td>
        
         <td>
           <div class="fotos-extra-container" data-id="${idBase}">
             ${fotosExtraHTML}
           </div>
         </td>
         <td><input type="text" class="editable-input nombre-input form-control form-control-sm" value="${nombre.replace(/"/g, '&quot;')}" data-id="${idBase}" data-campo="nombre" style="border-color: white;"></td>
         <td><input type="number" class="editable-input precio-input form-control form-control-sm" value="${precio}" data-id="${idBase}" data-campo="precio" step="0.01" min="0" style="width:80px; border-color: white;"></td>
          <td><input type="number" class="editable-input precio-anterior-input form-control form-control-sm" value="${precioAnterior}" data-id="${idBase}" data-campo="precio_anterior" step="0.01" min="0" style="width:80px; border-color: white;"></td>
          <td>${coloresCellHTML}</td>
          <td>${descripcionHTML}</td>
          <td>
            <div class="btn-group btn-group-sm">
              <button class="btn btn-warning btn-sm guardar-producto" data-id="${idBase}" title="Guardar">💾</button>
              <button class="btn btn-info btn-sm duplicar-producto" data-id="${idBase}" style="background-color:azure;" title="Duplicar">📋</button>
              <button class="btn btn-danger btn-sm eliminar-producto" data-id="${idBase}" title="Eliminar">🗑️</button>
            </div>
          </td>
        </tr>
    `;
  }).join('');
}

function mostrarSubgruposHorizontal(grupo) {
  const productos = window.todosLosProductos || [];
  const subgrupos = [...new Set(
    productos.filter(p => p.grupo === grupo)
             .map(p => p.subgrupo)
             .filter(Boolean)
  )];
  const barraSub = document.getElementById('adminSubgruposBar');
  if (!barraSub) return;

  let html = '';
  if (subgrupos.length > 0) {
    html = subgrupos.map(sub => `
      <button class="btn btn-sm btn-outline-secondary subgrupo-btn" data-grupo="${grupo}" data-subgrupo="${sub}">
        📂 ${sub}
      </button>
    `).join('');
  }
  html += `<button class="btn btn-sm btn-success agregar-subgrupo-btn" data-grupo="${grupo}" style="margin-left: 8px;">+ Subgrupo</button>`;

  barraSub.innerHTML = html;
  barraSub.style.display = 'flex';
  barraSub.dataset.currentGroup = grupo;
}


function ocultarSubgrupos() {
  const barraSub = document.getElementById('adminSubgruposBar');
  if (barraSub) barraSub.style.display = 'none';
}


async function agregarSubgrupo(grupo) {
  const nombreSubgrupo = prompt('Ingrese el nombre del nuevo subgrupo:');
  if (!nombreSubgrupo) return;

  const existe = window.todosLosProductos.some(p => p.grupo === grupo && p.subgrupo === nombreSubgrupo);
  if (existe) {
    alert('El subgrupo ya existe en este grupo.');
    return;
  }

  const tempId = 'nuevo_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  const nuevoProducto = {
    id_base: tempId,
    nombre: '(nuevo producto)',
    precio: 0,
    grupo: grupo,
    subgrupo: nombreSubgrupo,
    descripcion: '',
    imagen_url: '',
    fotos_adicionales: [],
  };
  window.todosLosProductos.push(nuevoProducto);
  filtrarProductos(grupo, null);
}


function filtrarProductos(grupo, subgrupo = null) {
  const productos = window.todosLosProductos || [];
  let filtrados = productos;
  if (grupo && grupo !== 'todos') {
    filtrados = productos.filter(p => p.grupo === grupo);
    if (subgrupo) {
      filtrados = filtrados.filter(p => p.subgrupo === subgrupo);
    }
  }
  const tbody = document.getElementById('tabla-productos-body');
  if (tbody) {
    tbody.innerHTML = renderFilasTabla(filtrados);
  }

  const grupoBtns = document.querySelectorAll('.grupo-btn');
  grupoBtns.forEach(btn => {
    if (btn.dataset.grupo === grupo) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  if (grupo && grupo !== 'todos') {
    const subgrupos = [...new Set(
      window.todosLosProductos.filter(p => p.grupo === grupo)
                              .map(p => p.subgrupo)
                              .filter(Boolean)
    )];
    if (subgrupos.length > 0) {
      mostrarSubgruposHorizontal(grupo);
    } else {
      ocultarSubgrupos();
    }
  } else {
    ocultarSubgrupos();
  }

  const subgrupoBtns = document.querySelectorAll('.subgrupo-btn');
  subgrupoBtns.forEach(btn => {
    if (btn.dataset.grupo === grupo && btn.dataset.subgrupo === subgrupo) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  window.currentAdminSubgrupo = subgrupo;
}


function obtenerProductoDesdeFila(fila, idBase) {
  const original = window.todosLosProductos.find(p => p.id_base === idBase) || {};
  const producto = { ...original };

  producto.nombre = fila.querySelector('.nombre-input')?.value || '';
  producto.precio = parseFloat(fila.querySelector('.precio-input')?.value) || 0;
  producto.precio_anterior = parseFloat(fila.querySelector('.precio-anterior-input')?.value) || 0; 
  producto.descripcion = fila.querySelector('.descripcion-textarea')?.value || '';

  const coloresContainer = fila.querySelector('.colores-stock-container');
  const variantes = {};
  const tallesSet = new Set();
  const coloresSet = new Set();

  if (coloresContainer) {
    const filasColor = coloresContainer.querySelectorAll('.fila-color');
    filasColor.forEach(filaColor => {
      const colorInput = filaColor.querySelector('.color-input');
      const toggle = filaColor.querySelector('.talle-toggle');
      const inputDinamico = filaColor.querySelector('.talles-input, .stock-input');
      if (!colorInput || !inputDinamico) return;

      const color = colorInput.value.trim();
      if (!color) return; 

      coloresSet.add(color);
      const esTalle = toggle?.checked || false;

      if (esTalle) {
        const tallesStr = inputDinamico.value;
        const tallesObj = parsearTallesStock(tallesStr);
        Object.entries(tallesObj).forEach(([talle, stock]) => {
          tallesSet.add(talle);
          const key = `${talle}_${color}`.replace(/ /g, '_');
          variantes[key] = {
            talle: talle,
            color: color,
            stock: stock,
            imagen_url: ''
          };
        });
      } else {
        let stock = parseInt(inputDinamico.value, 10);
        if (isNaN(stock)) stock = 0;
        const key = `unico_${color}`.replace(/ /g, '_');
        variantes[key] = {
          talle: 'unico',
          color: color,
          stock: stock,
          imagen_url: ''
        };
        tallesSet.add('unico');
      }
    });
  }

  producto.variantes = variantes;
  producto.tiene_variantes = Object.keys(variantes).length > 0;
  producto.talles = Array.from(tallesSet);
  producto.colores = Array.from(coloresSet);
  producto.stock = Object.values(variantes).reduce((sum, v) => sum + (v.stock || 0), 0);

  const fotosContainer = fila.querySelector('.fotos-extra-container');
  if (fotosContainer) {
    const imagenes = fotosContainer.querySelectorAll('img');
    const fotosUrls = [];
    imagenes.forEach(img => {
      const onclick = img.getAttribute('onclick');
      if (onclick) {
        const match = onclick.match(/openModal\('([^']+)'\)/);
        if (match) fotosUrls.push(match[1]);
      }
    });
    producto.fotos_adicionales = fotosUrls;
  }

  return producto;
}


async function recargarProductos() {
  try {
    const email = window.cliente?.email;
    if (!email) return;
    const resp = await fetch(`/api/productos?usuario=${encodeURIComponent(email)}`);
    const data = await resp.json();
    window.todosLosProductos = Array.isArray(data) ? data : [];
  } catch (err) {
  }
}


function getCurrentSelectedGroup() {
  const activeGroupBtn = document.querySelector('.grupo-btn.active');
  if (activeGroupBtn && activeGroupBtn.dataset.grupo !== 'todos') {
    return activeGroupBtn.dataset.grupo;
  }
  return null;
}


async function agregarNuevoProducto() {
  const grupoBtnActivo = document.querySelector('.grupo-btn.active');
  const grupoActual = grupoBtnActivo ? grupoBtnActivo.dataset.grupo : null;

  if (!grupoActual) {
    alert('Selecciona un grupo específico (no "Todos") para crear un producto en ese grupo, o crea un grupo primero.');
    return;
  }

  const subgrupoBtnActivo = document.querySelector('#adminSubgruposBar .subgrupo-btn.active');
  let subgrupoActual = '';

  if (subgrupoBtnActivo) {
    subgrupoActual = subgrupoBtnActivo.dataset.subgrupo;
  } else if (window.currentAdminSubgrupo) {
    subgrupoActual = window.currentAdminSubgrupo;
  } else {
  }

  const tempId = 'nuevo_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  const nuevoProducto = {
    id_base: tempId,
    nombre: '',
    precio: 0,
    grupo: grupoActual,
    subgrupo: subgrupoActual,
    descripcion: '',
    imagen_url: '',
    fotos_adicionales: [],
  };

  window.todosLosProductos.push(nuevoProducto);
  filtrarProductos(grupoActual, subgrupoActual);
}


async function guardarTodosProductos() {
  const filas = document.querySelectorAll('#tabla-productos-body tr');
  if (filas.length === 0) return;

  const productosAGuardar = [];
  filas.forEach(fila => {
    const idBase = fila.dataset.idBase;
    if (!idBase) return;
    const producto = obtenerProductoDesdeFila(fila, idBase);
    productosAGuardar.push(producto);
  });

  let guardados = 0;
  const errores = [];
  for (const producto of productosAGuardar) {
    try {
      const formDiv = { dataset: { idBase: producto.id_base } };
      const resultado = await guardarProducto(producto, formDiv, true); 
      if (resultado) guardados++;
    } catch (error) {
      errores.push(producto.nombre);
    }
  }

  await recargarProductos();
  renderTablaProductos();

  const mensaje = `Guardados ${guardados} de ${productosAGuardar.length} productos.`;
  if (errores.length) {
    alert(`${mensaje}\nErrores: ${errores.join(', ')}`);
  } else {
    alert(mensaje);
  }
}


function agregarNuevoGrupo() {
  const nombreGrupo = prompt('Ingrese el nombre del nuevo grupo:');
  if (!nombreGrupo) return;

  if (window.todosLosProductos.some(p => p.grupo === nombreGrupo)) {
    alert('El grupo ya existe.');
    return;
  }

  const nuevoProducto = {
    id_base: 'nuevo_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
    nombre: '(nuevo producto)',
    precio: 0,
    grupo: nombreGrupo,
    subgrupo: '',
    descripcion: '',
    imagen_url: '',
    fotos_adicionales: [],
  };
  window.todosLosProductos.push(nuevoProducto);
  renderTablaProductos();

  setTimeout(() => {
    const nuevoGrupoHeader = document.querySelector(`.grupo-btn[data-grupo="${nombreGrupo}"]`);
    if (nuevoGrupoHeader) {
      nuevoGrupoHeader.click();
    }
  }, 100);
}


if (window.modoAdmin) {
  const container = document.getElementById('adminFormsContainer');
  if (container) container.classList.remove('d-none');

  const formsList = document.getElementById('formsList');
  if (formsList) formsList.style.display = 'none';

  const configurarCA = document.getElementById('configurarCA');
  if (configurarCA) configurarCA.classList.remove('d-none');

  const tableView = document.getElementById('tableView');
  if (tableView) tableView.style.display = 'block';

  recargarProductos().then(() => {
    renderTablaProductos();
    setTimeout(() => {
      const primerGrupo = document.querySelector('.grupo-btn');
      if (primerGrupo) {
        primerGrupo.click();
      }
    }, 50);
  });

  const logoutWrapper = document.getElementById('logoutAdminWrapper');
  if (logoutWrapper) logoutWrapper.style.display = 'block';

  const configurarMP = document.getElementById('configurarMP');
  if (configurarMP) configurarMP.classList.remove('d-none');

  const loginToggleBtn = document.getElementById('loginToggleBtn');
  if (loginToggleBtn) loginToggleBtn.style.display = 'none';

  const adminContainer = document.getElementById('adminFormsContainer');
  if (adminContainer) {
    adminContainer.addEventListener('click', async (e) => {
      const target = e.target;

      if (target.id === 'guardarTodosTablaBtn') {
        e.preventDefault();
        await guardarTodosProductos();
        return;
      }

      if (target.id === 'btnNuevoProductoTabla') {
        e.preventDefault();
        agregarNuevoProducto();
        return;
      }

      if (target.id === 'adminBtnNuevoGrupo') {
        e.preventDefault();
        agregarNuevoGrupo();
        return;
      }

      if (target.classList.contains('agregar-subgrupo-btn')) {
        e.preventDefault();
        const grupo = target.dataset.grupo;
        if (grupo) agregarSubgrupo(grupo);
        return;
      }

      if (target.classList.contains('guardar-producto')) {
        e.preventDefault();
        const idBase = target.dataset.id;
        const fila = target.closest('tr');
        if (fila && idBase) {
          const producto = obtenerProductoDesdeFila(fila, idBase);
          await guardarProducto(producto, { dataset: { idBase } }, true);
        }
        return;
      }

      if (target.classList.contains('duplicar-producto')) {
        e.preventDefault();
        const idBase = target.dataset.id;
        if (idBase) duplicarProductoDesdeCard(idBase);
        return;
      }

      if (target.classList.contains('eliminar-producto')) {
        e.preventDefault();
        const idBase = target.dataset.id;
        if (idBase && confirm('¿Eliminar este producto?')) {
          eliminarProducto(idBase);
        }
        return;
      }

      if (target.classList.contains('agregar-fila-color')) {
        e.preventDefault();
        agregarFilaColor(target);
        return;
      }

      if (target.classList.contains('eliminar-foto-extra')) {
        e.preventDefault();
        const idBase = target.dataset.id;
        const url = target.dataset.url;
        if (idBase && url) eliminarFotoExtra(idBase, url);
        return;
      }

      if (target.classList.contains('agregar-foto-extra')) {
        e.preventDefault();
        agregarFotoExtra(target);
        return;
      }

      if (target.classList.contains('agregar-imagen-principal')) {
        e.preventDefault();
        agregarImagenPrincipal(target);
        return;
      }

      if (target.classList.contains('eliminar-color') || target.classList.contains('eliminar-fila-color')) {
        e.preventDefault();
        const filaColor = target.closest('.fila-color');
        if (filaColor) filaColor.remove();
        return;
      }

      if (target.classList.contains('grupo-btn')) {
        e.preventDefault();
        const grupo = target.dataset.grupo;
        if (grupo) filtrarProductos(grupo);
        return;
      }

      if (target.classList.contains('subgrupo-toggle-btn')) {
        e.preventDefault();
        const grupo = target.dataset.grupo;
        if (grupo) {
          const barraSub = document.getElementById('adminSubgruposBar');
          if (barraSub.style.display === 'flex' && barraSub.dataset.currentGroup === grupo) {
            ocultarSubgrupos();
          } else {
            mostrarSubgruposHorizontal(grupo);
            barraSub.dataset.currentGroup = grupo;
          }
        }
        return;
      }

      if (target.classList.contains('subgrupo-btn')) {
        e.preventDefault();
        const grupo = target.dataset.grupo;
        const subgrupo = target.dataset.subgrupo;
        if (grupo && subgrupo) filtrarProductos(grupo, subgrupo);
        return;
      }
    });
  }

  adminContainer.addEventListener('change', (e) => {
    const target = e.target;
    if (target.classList.contains('talle-toggle')) {
      const filaColor = target.closest('.fila-color');
      if (!filaColor) return;
      const inputDinamico = filaColor.querySelector('.talles-input, .stock-input');
      if (!inputDinamico) return;
      const estaMarcado = target.checked;
      if (estaMarcado) {
        let valorActual = inputDinamico.value;
        if (inputDinamico.type === 'number') {
          const stock = parseInt(valorActual, 10) || 0;
          valorActual = `unico:${stock}`;
        }
        inputDinamico.type = 'text';
        inputDinamico.classList.remove('stock-input');
        inputDinamico.classList.add('talles-input');
        inputDinamico.placeholder = 'S:30, M:20';
        inputDinamico.value = valorActual;
      } else {
        let valorActual = inputDinamico.value;
        let stock = 0;
        if (inputDinamico.type === 'text') {
          const tallesObj = parsearTallesStock(valorActual);
          if (tallesObj['unico']) {
            stock = tallesObj['unico'];
          } else {
            stock = Object.values(tallesObj).reduce((a, b) => a + b, 0);
          }
        } else {
          stock = parseInt(valorActual, 10) || 0;
        }
        inputDinamico.type = 'number';
        inputDinamico.classList.remove('talles-input');
        inputDinamico.classList.add('stock-input');
        inputDinamico.placeholder = 'Stock';
        inputDinamico.value = stock;
      }
    }
  });
}
