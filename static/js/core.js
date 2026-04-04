console.log = function() {};
const configWhatsApp = window.cliente?.whatsapp;
const email = window.cliente?.email;
const URL_BACKEND = "https://mpagina.onrender.com";
const usarFirestore = false;

let cargaCompleta = false;
let paginaActual = 1;
let productosFiltradosActuales = [];
let isMobile = window.matchMedia("(max-width: 767px)").matches;
let scrollTimer;
let isScrolling = false;
let urlProductos = `/api/productos?usuario=${encodeURIComponent(email)}`;
let pasoActual = 1;    
let envioCalculado = false;
let resizeTimer;  

if (window.modoAdmin && window.tokenAdmin) {
  urlProductos += `&token=${encodeURIComponent(window.tokenAdmin)}`;
}

function volverAlCarrito() {
  document.getElementById('pasoDireccion').style.display = 'none';
  document.getElementById('pasoCarrito').style.display = 'block';
  pasoActual = 1;
}

function volverADireccion() {
  document.getElementById('pasoDatos').style.display = 'none';
  document.getElementById('pasoDireccion').style.display = 'block';
  pasoActual = 2;
}

function vaciarCarrito() {
  window.carrito = [];
  actualizarCarrito();
  document.getElementById('pasoCarrito').style.display = 'block';
  document.getElementById('pasoDireccion').style.display = 'none';
  document.getElementById('pasoDatos').style.display = 'none';
  document.getElementById('costoEnvioMostrado').innerHTML = '';
  document.getElementById('btnSiguienteDatos').style.display = 'none';
  envioCalculado = false;
  pasoActual = 1;
  if (typeof window.resetEnvio === 'function') window.resetEnvio();
}

function mostrarPasoDireccion() {
  document.getElementById('pasoCarrito').style.display = 'none';
  document.getElementById('pasoDireccion').style.display = 'block';
  pasoActual = 2;
}

function mostrarPasoDatos() {
  if (!envioCalculado) {
    alert("Primero calculá el costo de envío.");
    return;
  }
  document.getElementById('pasoDireccion').style.display = 'none';
  document.getElementById('pasoDatos').style.display = 'block';
  pasoActual = 3;
}


function continuarSinEnvio() {
  window.costoEnvio = 0;
  document.getElementById("costoEnvioMostrado").innerHTML = "";
  if (typeof window.actualizarCarritoConEnvio === 'function') {
    window.actualizarCarritoConEnvio();
  }
  envioCalculado = true;
  mostrarPasoDatos();
}


function getVersionUrl(originalUrl, size) {
    if (originalUrl.includes('_500.webp')) {
        return originalUrl.replace('_500.webp', `_${size}.webp`);
    }
    const lastDot = originalUrl.lastIndexOf('.');
    if (lastDot === -1) return originalUrl; 
    const base = originalUrl.substring(0, lastDot);
    return base + `_${size}.webp`;
}

renderPagina(1, null);
fetch(urlProductos)
  .then(r => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then(lista => {
    const productosOrdenados = Array.isArray(lista) ? lista : [];
  
    productosOrdenados.sort((a, b) => {
      const stockA = (a.stock_por_talle && Object.values(a.stock_por_talle).some(v => v > 0)) || 
                     (a.stock && a.stock > 0);
      const stockB = (b.stock_por_talle && Object.values(b.stock_por_talle).some(v => v > 0)) || 
                     (b.stock && b.stock > 0);
      
      if (stockA && !stockB) return -1;
      if (!stockA && stockB) return 1;
      
      return (a.precio || 0) - (b.precio || 0);
    });
    
    window.todosLosProductos = productosOrdenados;

    const cont = document.getElementById("productos");
    const contGrupos = document.getElementById("panelGrupos");
    const contSub = document.getElementById("panelSubcategorias");

    if (!cont) return;

    const grupos = [...new Set(window.todosLosProductos.map(p => p.grupo).filter(Boolean))];

    if (contGrupos) {
      contGrupos.innerHTML = ""; 
      grupos.forEach(g => {
        const btn = document.createElement("button");
        btn.className = "btn-grupo";
        btn.textContent = g;
        btn.addEventListener("click", (e) => {
          mostrarGrupo(g, e);
        });
        contGrupos.appendChild(btn);
      });
    }

    const primerGrupo = grupos[0];
    const subgruposPrimer = [...new Set(window.todosLosProductos
      .filter(p => p.grupo === primerGrupo)
      .map(p => p.subgrupo).filter(Boolean))];

    if (primerGrupo) {
      if (subgruposPrimer.length > 0) {
        filtrarSubcategoria(primerGrupo, subgruposPrimer[0]);
      } else {
        mostrarGrupo(primerGrupo, null, true);
      }
    }

  })
  .catch(err => {
    cargaCompleta = true;
    const cont = document.getElementById("productos");
    if (cont) cont.innerHTML = "<p class='text-danger text-center'>Error al cargar productos. Intenta de nuevo.</p>";
  });


function renderPagina(pagina, productos) {
  const cont = document.getElementById("productos");
  if (!cont) return;
  const itemsPorPagina = getItemsPorPagina();

  if (!productos || productos.length === 0) {
    cont.innerHTML = '<div class="text-center mt-5"><div class="spinner-border text-light" role="status"></div><p>Cargando productos...</p></div>';
    return;
  }

  const inicio = (pagina - 1) * itemsPorPagina;
  const fin = Math.min(inicio + itemsPorPagina, productos.length);
  const productosPagina = productos.slice(inicio, fin);

  const fragment = document.createDocumentFragment();
  productosPagina.forEach((p, index) => {
    const esLCP = (pagina === 1 && index === 0);
    fragment.appendChild(renderProducto(p, esLCP));
  });

  cont.innerHTML = '';
  cont.appendChild(fragment);
}


function renderPaginacion(productosFiltrados) {
  const pagDiv = document.getElementById("paginacion");
  if (!pagDiv) return;
  
  const itemsPorPagina = getItemsPorPagina(); 
  const totalPaginas = Math.ceil(productosFiltrados.length / itemsPorPagina);
  
  pagDiv.innerHTML = "";
  for (let i = 1; i <= totalPaginas; i++) {
    const btn = document.createElement("button");
    btn.textContent = i;
    btn.className = "btn btn-light mx-1";
    if (i === paginaActual) {
      btn.classList.add("active");
    }
    btn.onclick = () => {
      paginaActual = i;
      renderPagina(i, productosFiltrados);
      renderPaginacion(productosFiltrados);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    pagDiv.appendChild(btn);
  }
}


function actualizarCarritoConEnvio() {
  const totalSpan = document.getElementById('totalCarrito');
  if (!totalSpan) return;

  // Calcular el subtotal de los productos (sin envío)
  let subtotal = 0;
  if (window.carrito && window.carrito.length > 0) {
    subtotal = window.carrito.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
  }

  const costoEnvio = window.costoEnvio || 0;
  const totalConEnvio = subtotal + costoEnvio;

  const fmt = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  totalSpan.textContent = fmt.format(totalConEnvio);

  // Opcional: mostrar el desglose en algún lugar
  const envioSpan = document.getElementById('costoEnvioMostrado');
  if (envioSpan && costoEnvio > 0) {
    envioSpan.innerHTML = `<strong>Envío:</strong> $${costoEnvio.toFixed(2)}`;
  } else if (envioSpan && costoEnvio === 0) {
    envioSpan.innerHTML = '';
  }
}

function resetEnvio() {
  window.costoEnvio = 0;
  envioCalculado = false;
  const costoEnvioSpan = document.getElementById('costoEnvioMostrado');
  if (costoEnvioSpan) costoEnvioSpan.innerHTML = '';
  const btnSiguiente = document.getElementById('btnSiguienteDatos');
  if (btnSiguiente) btnSiguiente.style.display = 'none';
}

function renderProducto(p, esLCP = false) {
  const template = document.getElementById('producto-template');
  const card = template.content.cloneNode(true).firstElementChild;
  
  // Asignar ID y dataset
  card.dataset.id = p.id_base;
  card.dataset.precio = p.precio;

  const precioActual = parseFloat(p.precio) || 0;
  let precioAnterior = parseFloat(p.precio_anterior) || 0;
  let esOferta = precioAnterior > 0 && precioAnterior > precioActual;
  let descuentoPorcentaje = esOferta ? Math.round(((precioAnterior - precioActual) / precioAnterior) * 100) : 0;

  // Elementos del DOM
  const ofertaBadge = card.querySelector('.oferta-badge');
  const btnGirar = card.querySelector('.btn-girar');
  const img = card.querySelector('img');
  const titulo = card.querySelector('.card-title');
  const precioSpan = card.querySelector('.precio-actual');
  const precioAnteriorSpan = card.querySelector('.precio-anterior-tachado');
  const ahorroSmall = card.querySelector('.ahorro');
  const selectoresContainer = card.querySelector('.selectores-container');
  const cantidadInput = card.querySelector('input[type="number"]');
  const agregarBtn = card.querySelector('.btn-secondary.btn-sm');
  const fotosAdicionalesDiv = card.querySelector('.fotos-adicionales');
  const whatsappContainer = card.querySelector('.whatsapp-container');
  const btnReversa = card.querySelector('.btn-reversa');
  const descripcionTexto = card.querySelector('.descripcion-texto');
  const coloresInfo = card.querySelector('.colores-info');
  const tallesInfo = card.querySelector('.talles-info');
  const btnVolver = card.querySelector('.card-back-footer .btn-secondary');

  // Configurar imagen
  const imagenGrande = p.imagen_url || '/static/img/fallback.webp';
  const imagenCard = getVersionUrl(imagenGrande, '180');
  img.src = imagenCard;
  if (!esLCP) img.setAttribute('data-src', imagenCard);
  img.alt = p.nombre;
  img.onload = function() { this.style.opacity = '1'; };
  img.onclick = () => openModal(imagenGrande);
  if (esLCP) img.loading = 'eager';
  else img.loading = 'lazy';

  // Título
  titulo.textContent = p.nombre;

  // Precios y oferta
  precioSpan.textContent = p.precio;
  precioSpan.id = `precio_${p.id_base}`; 
  if (esOferta) {
    precioAnteriorSpan.style.display = 'inline';
    precioAnteriorSpan.textContent = `$${precioAnterior.toFixed(2)}`;
    ahorroSmall.style.display = 'inline';
    ahorroSmall.textContent = ` Ahorras $${(precioAnterior - precioActual).toFixed(2)}`;
    ofertaBadge.style.display = 'block';
    ofertaBadge.textContent = `🔥 OFERTA -${descuentoPorcentaje}%`;
    precioSpan.style.color = '#ff4757';
    precioSpan.style.fontWeight = 'bold';
  } else {
    precioAnteriorSpan.style.display = 'none';
    ahorroSmall.style.display = 'none';
    ofertaBadge.style.display = 'none';
  }

  // Descripción
  if (p.descripcion) {
    descripcionTexto.innerHTML = `<div style="font-size:1rem; line-height:1.5; color:#f8f9fa; white-space:pre-line;">${p.descripcion}</div>`;
  } else {
    descripcionTexto.innerHTML = `<div style="font-size:1rem; color:#adb5bd; font-style:italic;">Este producto no tiene descripción adicional.</div>`;
  }

  // Colores y talles (igual que antes, usando las mismas variables)
  const variantes = p.variantes || {};
  const colores = p.colores || [];
  const tallesUnicos = p.talles || [];
  const tieneColores = colores.length > 0 && !(colores.length === 1 && colores[0] === "unico");
  const tallesPorColor = {};
  colores.forEach(color => { tallesPorColor[color] = {}; });
  Object.values(variantes).forEach(v => {
    if (v.color && v.talle && tallesPorColor[v.color]) {
      tallesPorColor[v.color][v.talle] = v.stock;
    }
  });

  if (!tieneColores) {
    const talles = tallesUnicos.length ? tallesUnicos : ["unico"];
    const stockMap = p.stock_por_talle || {};
    tallesPorColor["unico"] = {};
    talles.forEach(t => { tallesPorColor["unico"][t] = stockMap[t] || 0; });
    colores.push("unico");
  }

  const colorInicial = colores[0];
  const tallesIniciales = tallesPorColor[colorInicial] || {};
  const opcionesTallesIniciales = Object.entries(tallesIniciales).map(([t, stock]) => {
    return stock > 0 ? `<option value="${t}">${t} (${stock} disponible${stock !== 1 ? 's' : ''})</option>` : `<option value="${t}" disabled>${t} (Agotado)</option>`;
  }).join('');
  let primerTalleConStock = Object.entries(tallesIniciales).find(([_, stock]) => stock > 0)?.[0] || "";
  let stockInicial = primerTalleConStock ? tallesIniciales[primerTalleConStock] : 0;

  // Selectores de color/talle
  let selectoresHTML = "";
  if (tieneColores) {
    selectoresHTML += `<div class="mb-2 d-flex align-items-center gap-2">
      <span id="color-label-${p.id_base}" class="mb-0"><strong>Color:</strong></span>
      <select id="color_${p.id_base}" class="form-select form-select-sm w-auto" style="min-width:190px;" aria-labelledby="color-label-${p.id_base}">
        ${colores.map(color => `<option value="${color}">${color}</option>`).join('')}
      </select>
    </div>`;
  }
  selectoresHTML += `<div class="mb-2 d-flex align-items-center gap-2">
    <span id="talle-label-${p.id_base}" class="mb-0"><strong>Talle:</strong></span>
    <select id="talle_${p.id_base}" class="form-select form-select-sm w-auto" style="min-width:190px;" aria-labelledby="talle-label-${p.id_base}">
      ${opcionesTallesIniciales || '<option>Sin talles disponibles</option>'}
    </select>
  </div>`;
  selectoresContainer.innerHTML = selectoresHTML;

  // Configurar inputs y botones
  cantidadInput.id = `cantidad_${p.id_base}`;
  cantidadInput.setAttribute('aria-label', `Cantidad de ${p.nombre}`);
  cantidadInput.max = stockInicial > 0 ? stockInicial : 1;
  cantidadInput.disabled = stockInicial <= 0;
  agregarBtn.id = `btn_agregar_${p.id_base}`;
  agregarBtn.disabled = stockInicial <= 0;
  if (stockInicial <= 0) agregarBtn.style.opacity = '0.5';
  agregarBtn.textContent = stockInicial > 0 ? "Agregar al carrito" : "❌ Sin stock";

  // Evento de agregar al carrito (onclick dinámico)
  const nombreEscapado = p.nombre.replace(/'/g, "\\'").replace(/"/g, '\\"');
  const imagenGrandeEscapada = imagenGrande.replace(/'/g, "\\'");
  const grupoEscapado = (p.grupo || "").replace(/'/g, "\\'");
  const subgrupoEscapado = (p.subgrupo || "").replace(/'/g, "\\'");
  agregarBtn.onclick = () => {
    agregarAlCarritoConColor(nombreEscapado, `precio_${p.id_base}`, `cantidad_${p.id_base}`, p.id_base, grupoEscapado, subgrupoEscapado, imagenGrandeEscapada, `color_${p.id_base}`, `talle_${p.id_base}`);
  };

  // Fotos adicionales
  if (p.fotos_adicionales && p.fotos_adicionales.length) {
    let fotosHTML = '<div class="d-flex flex-wrap mt-1" style="gap:3px;">';
    p.fotos_adicionales.forEach(foto => {
      const miniatura = getVersionUrl(foto, '58');
      fotosHTML += `<img src="${miniatura}" alt="Foto adicional de ${p.nombre}" style="width:40px; height:40px; object-fit:cover; border-radius:3px; cursor:pointer;" onclick="openModal('${foto}')">`;
    });
    fotosHTML += '</div>';
    fotosAdicionalesDiv.innerHTML = fotosHTML;
  } else {
    fotosAdicionalesDiv.innerHTML = '';
  }

  // WhatsApp
  let whatsappUrl = configWhatsApp;
  if (configWhatsApp && configWhatsApp.includes("wa.me")) {
    const mensaje = encodeURIComponent(`Hola! Me interesa el producto: "${p.nombre}" - Precio: $${p.precio}\n\n¿Podrías darme más información?`);
    const match = configWhatsApp.match(/wa\.me\/(\d+)/);
    if (match) {
      const numero = match[1];
      whatsappUrl = `https://wa.me/${numero}?text=${mensaje}`;
    } else {
      whatsappUrl = `${configWhatsApp}?text=${mensaje}`;
    }
  }
  if (whatsappUrl) {
    whatsappContainer.innerHTML = `<a href="${whatsappUrl}" class="btn btn-whatsapp btn-sm w-100 d-flex align-items-center justify-content-center gap-2" target="_blank" style="background-color:#0c6909; color:white;"><img src="/static/img/whatsapp.webp" alt="WhatsApp" style="width:20px; height:20px;">Consultar</a>`;
  } else {
    whatsappContainer.innerHTML = '';
  }

  // Información de colores/talles en el reverso
  if (tieneColores) {
    coloresInfo.style.display = 'block';
    coloresInfo.innerHTML = `<strong>Colores:</strong> ${colores.join(", ")}`;
  } else {
    coloresInfo.style.display = 'none';
  }
  if (tallesUnicos.length > 0 && tallesUnicos[0] !== "unico") {
    tallesInfo.style.display = 'block';
    tallesInfo.innerHTML = `<strong>Talles:</strong> ${tallesUnicos.join(", ")}`;
  } else {
    tallesInfo.style.display = 'none';
  }

  // Eventos de girar card
  btnGirar.onclick = () => girarCard(btnGirar);
  btnReversa.onclick = () => girarCard(btnReversa);
  btnVolver.onclick = () => girarCard(btnVolver);

  // Lógica de selección de color/talle (solo si tiene colores)
  if (tieneColores) {
    const colorSelect = card.querySelector(`#color_${p.id_base}`);
    const talleSelect = card.querySelector(`#talle_${p.id_base}`);
    const actualizarTallesPorColor = (color) => {
      const tallesDelColor = tallesPorColor[color] || {};
      const opciones = Object.entries(tallesDelColor).map(([t, stock]) => {
        return stock > 0 ? `<option value="${t}">${t} (${stock} disponible${stock !== 1 ? 's' : ''})</option>` : `<option value="${t}" disabled>${t} (Agotado)</option>`;
      }).join('');
      talleSelect.innerHTML = opciones || '<option>Sin talles disponibles</option>';
      const primerTalleConStock = Object.entries(tallesDelColor).find(([_, stock]) => stock > 0)?.[0] || "";
      if (primerTalleConStock) {
        talleSelect.value = primerTalleConStock;
        const stockDisponible = tallesDelColor[primerTalleConStock];
        cantidadInput.max = stockDisponible;
        cantidadInput.disabled = stockDisponible <= 0;
        cantidadInput.value = Math.min(parseInt(cantidadInput.value) || 1, stockDisponible);
        agregarBtn.disabled = stockDisponible <= 0;
        agregarBtn.textContent = stockDisponible > 0 ? "Agregar al carrito" : "❌ Sin stock";
      } else {
        cantidadInput.disabled = true;
        agregarBtn.disabled = true;
        agregarBtn.textContent = "❌ Sin stock";
      }
    };
    colorSelect.addEventListener('change', (e) => actualizarTallesPorColor(e.target.value));
    talleSelect.addEventListener('change', (e) => {
      const color = colorSelect.value;
      const talle = e.target.value;
      const stockDisponible = tallesPorColor[color]?.[talle] || 0;
      cantidadInput.max = stockDisponible;
      cantidadInput.disabled = stockDisponible <= 0;
      cantidadInput.value = Math.min(parseInt(cantidadInput.value) || 1, stockDisponible);
      agregarBtn.disabled = stockDisponible <= 0;
      agregarBtn.textContent = stockDisponible > 0 ? "Agregar al carrito" : "❌ Sin stock";
    });
    actualizarTallesPorColor(colorInicial);
  } else {
    // Sin colores, solo talles (sin setTimeout)
    const talleSelect = card.querySelector(`#talle_${p.id_base}`);
    if (talleSelect) {
      const tallesMap = p.stock_por_talle || {};
      if (p.variantes && Object.keys(p.variantes).length > 0) {
        const tallesUnicosVar = [...new Set(Object.values(p.variantes).map(v => v.talle))];
        const opciones = tallesUnicosVar.map(t => {
          const stock = Object.values(p.variantes).find(v => v.talle === t)?.stock || 0;
          return `<option value="${t}" ${stock > 0 ? '' : 'disabled'}>${t} (${stock} disponible)</option>`;
        }).join('');
        talleSelect.innerHTML = opciones;
      }
      talleSelect.addEventListener('change', (e) => {
        actualizarStockPorTalle(p.id_base, e.target.value);
      });
      let primerTalle = null;
      if (p.variantes && Object.keys(p.variantes).length > 0) {
        primerTalle = Object.values(p.variantes).find(v => v.stock > 0)?.talle;
      } else {
        primerTalle = Object.keys(tallesMap).find(t => tallesMap[t] > 0);
      }
      if (primerTalle) {
        talleSelect.value = primerTalle;
        actualizarStockPorTalle(p.id_base, primerTalle);
      } else {
        actualizarStockPorTalle(p.id_base, talleSelect.value);
      }
    }
  }

  requestAnimationFrame(() => card.classList.add("show"));
  setTimeout(() => card.classList.remove("fade-reorder"), 50);

  return card;
}

function openModal(src) {
  const modal = document.getElementById("imgModal");
  document.getElementById("modal-img").src = src;
  modal.style.display = "flex";
  setTimeout(() => modal.classList.add("show"), 10); 
}
   

function closeModal() {
  const modal = document.getElementById("imgModal");
  modal.classList.remove("show");
  setTimeout(() => modal.style.display = "none", 300);
}


function mostrarGrupo(nombre, event, auto = false) {
  const grupoCanon = String(nombre || "").trim();
  window.currentGrupo = grupoCanon.toLowerCase();
  window.currentSub = null; 

  const cont = document.getElementById("productos");
  if (!cont) return;

  document.querySelectorAll('.btn-grupo').forEach(btn => btn.classList.remove('active'));
  if (event?.target) {
    event.target.classList.add('active');
  }

  const panel = document.getElementById('panelSubcategorias');
  if (!panel) return;
  panel.innerHTML = "";

  const productosGrupo = (window.todosLosProductos || []).filter(
    p => String(p.grupo || "").toLowerCase() === window.currentGrupo
  );

  const subcategorias = [...new Set(
    productosGrupo.map(p => p.subgrupo).filter(s => s && String(s).toLowerCase() !== 'general')
  )];

  subcategorias.forEach(sub => {
    const btn = document.createElement('button');
    btn.textContent = sub;
    btn.className = 'btn-subgrupo';
    btn.addEventListener("click", (e) => mostrarSubgrupo(sub, e));
    panel.appendChild(btn);
  });

  paginaActual = 1;
  renderPagina(1, productosGrupo);
  renderPaginacion(productosGrupo);

  if (subcategorias.length > 0) {
    if (!auto) {
      panel.classList.remove('oculta');
    } else {
      panel.classList.add('oculta');
    }
  } else {
    panel.classList.add('oculta');
  }
  setTimeout(() => {
    ajustarPosicionesPaneles(); 

    if (typeof gestionarFlechas === 'function') {
      gestionarFlechas('panelSubcategorias');
      gestionarFlechas('panelGrupos');
    }
  }, 0);
  setTimeout(() => window.scrollTo({ top: 0, behavior: 'auto' }), 0);
}
window.mostrarGrupo = mostrarGrupo;


function filtrarSubcategoria(grupo, subgrupo) {
  const cont = document.getElementById("productos");
  if (!cont) return;

  const grupoCanon = String(grupo || "").trim().toLowerCase();
  const subCanon = String(subgrupo || "").trim().toLowerCase();

  window.currentGrupo = grupoCanon;
  window.currentSub = subCanon || null; 

  document.querySelectorAll('.btn-subgrupo').forEach(btn => btn.classList.remove('active'));

  if (subCanon) {
    const btnSub = Array.from(document.querySelectorAll('.btn-subgrupo'))
      .find(btn => btn.textContent.trim().toLowerCase() === subCanon);
    if (btnSub) btnSub.classList.add('active');
  }

  let productosFiltrados;
  if (subCanon) {
    productosFiltrados = window.todosLosProductos.filter(p =>
      String(p.grupo || "").toLowerCase() === grupoCanon &&
      String(p.subgrupo || "").toLowerCase() === subCanon
    );
  } else {
    productosFiltrados = window.todosLosProductos.filter(p =>
      String(p.grupo || "").toLowerCase() === grupoCanon
    );
  }

  paginaActual = 1;
  renderPagina(1, productosFiltrados);
  renderPaginacion(productosFiltrados);

  setTimeout(() => window.scrollTo({ top: 0, behavior: 'auto' }), 0);
}
window.filtrarSubcategoria = filtrarSubcategoria;


(function setupImmediate() {
  const panelSubcategorias = document.getElementById('panelSubcategorias');
  const panelGrupos = document.getElementById('panelGrupos');
  if (panelSubcategorias) panelSubcategorias.classList.add('oculta');
  if (panelGrupos) panelGrupos.classList.add('oculta');

  const toggleBtn = document.getElementById('toggleCarrito');
  if (toggleBtn) {
    toggleBtn.onclick = function() {
      const carritoDiv = document.getElementById('carrito');
      if (!carritoDiv) return;

      const isVisible = window.getComputedStyle(carritoDiv).display !== 'none';
      carritoDiv.style.display = isVisible ? 'none' : 'block';
    };
  } else {
    setTimeout(setupImmediate, 50);
  }
})();  


function mostrarSubgrupo(subgrupo, event) {
  const grupoActivoBtn = document.querySelector('.btn-grupo.active');
  const grupoActivo = grupoActivoBtn ? grupoActivoBtn.textContent.trim() : null;

  if (!grupoActivo) {
    return;
  }

  document.querySelectorAll('.btn-subgrupo').forEach(btn => btn.classList.remove('active'));
  if (event?.target) {
    event.target.classList.add('active');
  }

  const grupoCanon = String(grupoActivo).trim();
  const subCanon = String(subgrupo || "").trim();

  window.currentGrupo = grupoCanon.toLowerCase();
  window.currentSub = subCanon.toLowerCase();

  filtrarSubcategoria(grupoCanon, subCanon);
}
window.mostrarSubgrupo = mostrarSubgrupo;


function sincronizarPreciosDelCarrito() {
  window.carrito.forEach(item => {
    const idPrecio = "precio_" + (item.id_base || item.nombre.replace(/ /g, "_"));
    const precioSpan = document.getElementById(idPrecio);
    if (precioSpan) {
      const precioActual = parseFloat(precioSpan.textContent);
      if (!isNaN(precioActual)) {
        item.precio = precioActual;
      }
    }
  });
}


function actualizarCarrito(conAnimacion = false) {
  sincronizarPreciosDelCarrito();

  const lista = document.getElementById('listaCarrito');
  const totalSpan = document.getElementById('totalCarrito');
  if (!lista || !totalSpan) return;

  lista.innerHTML = '';
  let suma = 0;

  if (window.carrito.length === 0) {
    lista.innerHTML = "<li>🛒 Carrito vacío</li>";
    totalSpan.textContent = "0.00";
    const contadorSpan = document.getElementById('carrito-contador');
    if (contadorSpan) {
      contadorSpan.textContent = '0';
      contadorSpan.style.background = '#888';
    }
    return;
  }

  const fmt = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const escape = str => (str || '').replace(/'/g, "\\'");

  window.carrito.forEach(item => {
    const subtotal = item.precio * item.cantidad;
    suma += subtotal;

    let descripcion = item.nombre;
    const tieneColor = item.color && item.color !== "unico";
    const tieneTalle = item.talle && item.talle !== "unico";

    if (tieneColor && tieneTalle) {
      descripcion += ` (Color: ${item.color} - Talle: ${item.talle})`;
    } else if (tieneColor) {
      descripcion += ` (Color: ${item.color})`;
    } else if (tieneTalle) {
      descripcion += ` (Talle: ${item.talle})`;
    }

    lista.insertAdjacentHTML("beforeend", `
      <li style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <div>
          <div><strong>${descripcion}</strong></div>
          <div style="font-size: 0.9em; color: #666;">
            ${item.cantidad} x $${item.precio.toFixed(2)} = $${subtotal.toFixed(2)}
          </div>
        </div>
        <button onmousedown="eliminarDelCarrito('${escape(item.id_base)}', '${escape(item.talle)}', '${escape(item.color)}', event)" 
                style="background: none; border: none; color: red; font-weight: bold; font-size: 16px; cursor: pointer;">
          ❌
        </button>
      </li>`);
  });

  totalSpan.textContent = fmt.format(suma);

  const contadorSpan = document.getElementById('carrito-contador');
  if (contadorSpan) {
    const totalItems = window.carrito.reduce((acc, item) => acc + item.cantidad, 0);
    contadorSpan.textContent = totalItems;
    contadorSpan.style.background = totalItems > 0 ? '#ff4757' : '#888';

    if (conAnimacion) {
      contadorSpan.classList.add('pop-animation');
      setTimeout(() => contadorSpan.classList.remove('pop-animation'), 400);
    }
  }
}


function agregarAlCarritoConColor(nombre, idPrecioSpan, idCantidad, id_base, grupo, subgrupo, imagenUrl, idColorSelect, idTalleSelect) {
  const cantidadInput = document.getElementById(idCantidad);
  const precioSpan = document.getElementById(idPrecioSpan);
  const colorSelect = document.getElementById(idColorSelect);
  const talleSelect = document.getElementById(idTalleSelect);

  if (!cantidadInput || !precioSpan) {
    alert("❌ Error: No se pudieron obtener los datos del producto");
    return;
  }

  const colorElegido = colorSelect ? colorSelect.value : "unico";
  const talleElegido = talleSelect ? talleSelect.value : "unico";

  if (colorSelect && !colorElegido) {
    alert("❌ Debes seleccionar un color");
    return;
  }
  if (talleSelect && !talleElegido) {
    alert("❌ Debes seleccionar un talle");
    return;
  }

  const productoOriginal = window.todosLosProductos.find(p => p.id_base === id_base);
  if (!productoOriginal) {
    alert("❌ Producto no encontrado");
    return;
  }

  const variantes = productoOriginal.variantes || {};
  let stockDisponible = 0;
  for (const key in variantes) {
    const varObj = variantes[key];
    if (varObj.talle === talleElegido && varObj.color === colorElegido) {
      stockDisponible = varObj.stock;
      break;
    }
  }

  if (stockDisponible <= 0) {
    alert(`❌ No hay stock disponible para ${colorElegido} - ${talleElegido}`);
    return;
  }

  const cantidad = parseInt(cantidadInput.value) || 1;
  if (cantidad > stockDisponible) {
    alert(`❌ Solo hay ${stockDisponible} unidades disponibles para ${colorElegido} - ${talleElegido}`);
    cantidadInput.value = stockDisponible;
    return;
  }

  const precio = parseFloat(precioSpan.textContent.replace("$", "").replace(",", "")) || 0;

  const existente = window.carrito.find(item => 
    item.id_base === id_base && 
    item.talle === talleElegido && 
    item.color === colorElegido
  );

  if (existente) {
    const nuevoTotal = existente.cantidad + cantidad;
    if (nuevoTotal > stockDisponible) {
      alert(`❌ No puedes llevar más de ${stockDisponible} unidades de ${colorElegido} - ${talleElegido}`);
      return;
    }
    existente.cantidad = nuevoTotal;
  } else {
    const nuevoItem = {
      nombre,
      precio,
      cantidad,
      id_base,
      talle: talleElegido,
      color: colorElegido,
      grupo,
      subgrupo,
      imagen_url: imagenUrl
    };
    window.carrito.push(nuevoItem);
  }

  actualizarCarrito(true);
  mostrarToast(`✅ ${nombre} (${colorElegido} - ${talleElegido}) agregado al carrito`);
}


function actualizarStockPorTalle(idProducto, talleSeleccionado) {
  const cantidadInput = document.getElementById(`cantidad_${idProducto}`);
  const agregarBtn = document.getElementById(`btn_agregar_${idProducto}`);
  if (!cantidadInput || !agregarBtn) {
    return;
  }

  const producto = window.todosLosProductos?.find(p => p.id_base === idProducto);
  if (!producto) {
    return;
  }

  let stockDisponible = 0;

  if (producto.variantes && Object.keys(producto.variantes).length > 0) {
    const variantes = producto.variantes;
    for (const key in variantes) {
      if (variantes[key].talle === talleSeleccionado) {
        stockDisponible = variantes[key].stock;
        break;
      }
    }
  }
  else if (producto.stock_por_talle && typeof producto.stock_por_talle === 'object') {
    stockDisponible = producto.stock_por_talle[talleSeleccionado] || 0;
  }
  else if (producto.stock !== undefined) {
    stockDisponible = producto.stock;
  }

  cantidadInput.max = stockDisponible;
  if (stockDisponible > 0) {
    cantidadInput.disabled = false;
    const valorActual = parseInt(cantidadInput.value) || 1;
    cantidadInput.value = Math.min(valorActual, stockDisponible);
    agregarBtn.disabled = false;
    agregarBtn.style.opacity = "1";
    agregarBtn.textContent = "Agregar al carrito";
  } else {
    cantidadInput.disabled = true;
    cantidadInput.value = 0;
    agregarBtn.disabled = true;
    agregarBtn.style.opacity = "0.5";
    agregarBtn.textContent = "❌ Sin stock";
  }
}


function habilitarScrollHorizontal(selector) {
  const panel = document.querySelector(selector);
  if (!panel) return;

  panel.addEventListener('wheel', (e) => {
    e.preventDefault(); 
    panel.scrollBy({
      left: e.deltaY,
      behavior: 'smooth' 
    });
  });
  let isDown = false;
  let startX;
  let scrollLeft;

  panel.addEventListener('mousedown', (e) => {
    isDown = true;
    panel.classList.add('active'); 
    startX = e.pageX - panel.offsetLeft;
    scrollLeft = panel.scrollLeft;
  });

  panel.addEventListener('mouseleave', () => {
    isDown = false;
    panel.classList.remove('active');
  });

  panel.addEventListener('mouseup', () => {
    isDown = false;
    panel.classList.remove('active');
  });

  panel.addEventListener('mousemove', (e) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - panel.offsetLeft;
    const walk = (x - startX); 
    panel.scrollLeft = scrollLeft - walk;
  });
}


habilitarScrollHorizontal('.panel-grupos');
habilitarScrollHorizontal('.panel-subcategorias');


isMobile = window.matchMedia("(max-width: 767px)").matches;
window.matchMedia("(max-width: 767px)").addEventListener('change', (e) => {
    isMobile = e.matches;
    if (productosFiltradosActuales && productosFiltradosActuales.length > 0) {
        renderPagina(paginaActual, productosFiltradosActuales);
        renderPaginacion(productosFiltradosActuales);
    }
  
    if (typeof ajustarPosicionesPaneles === 'function') {
        ajustarPosicionesPaneles();
    }
});



function eliminarDelCarrito(id_base, talle, event) {
  if (event?.stopPropagation) event.stopPropagation();

  window.carrito = window.carrito.filter(p => {
    if (talle && talle !== "unico") {
      return !(p.id_base === id_base && p.talle === talle);
    } else {
      return p.id_base !== id_base;
    }
  });

  actualizarCarrito();
}


function gestionarFlechas(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;

  const contenedor = panel.parentElement;
  const flechaIzq = contenedor.querySelector('.flecha-izq');
  const flechaDer = contenedor.querySelector('.flecha-der');

  if (!flechaIzq || !flechaDer) return;

  if (panel.classList.contains('oculta')) {
    flechaIzq.style.display = 'none';
    flechaDer.style.display = 'none';
    return;
  }

  const actualizarVisibilidad = () => {
    flechaIzq.style.display = panel.scrollLeft > 5 ? 'flex' : 'none';
    const tieneMas = panel.scrollLeft + panel.clientWidth < panel.scrollWidth - 5;
    flechaDer.style.display = tieneMas ? 'flex' : 'none';
  };

  panel.onscroll = actualizarVisibilidad;
  window.onresize = actualizarVisibilidad; 

  flechaIzq.onclick = () => panel.scrollBy({ left: -200, behavior: 'smooth' });
  flechaDer.onclick = () => panel.scrollBy({ left: 200, behavior: 'smooth' });

  actualizarVisibilidad();
}


function girarCard(elemento) {
  const cardContenedor = elemento.closest('.card-contenedor');
  if (cardContenedor) {
    const estaGirada = cardContenedor.style.transform === 'rotateY(180deg)';
    cardContenedor.style.transform = estaGirada ? 'rotateY(0deg)' : 'rotateY(180deg)';
  }
}


function mostrarToast(mensaje) {
  const toastAnterior = document.querySelector('.toast-notificacion');
  if (toastAnterior) toastAnterior.remove();

  const toast = document.createElement('div');
  toast.className = 'toast-notificacion';
  toast.textContent = mensaje;
  toast.style.cssText = `
    position: fixed;
    bottom: 90px;
    right: 20px;
    background: rgba(0, 0, 0, 0.9);
    backdrop-filter: blur(10px);
    color: white;
    padding: 12px 20px;
    border-radius: 30px;
    font-family: 'Raleway', sans-serif;
    font-size: 14px;
    z-index: 9999;
    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    border: 1px solid rgba(255,255,255,0.1);
    transform: translateX(400px);
    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  `;
  document.body.appendChild(toast);

  toast.offsetHeight;
  toast.style.transform = 'translateX(0)';

  setTimeout(() => {
    toast.style.transform = 'translateX(400px)';
    setTimeout(() => toast.remove(), 300);
  }, 2000);
}


function mostrarTodos() {
    const panelGrupos = document.getElementById('panelGrupos');
    const panelSub = document.getElementById('panelSubcategorias');
    if (!panelGrupos || !panelSub) return;

    panelGrupos.classList.toggle('oculta');
    
    if (!panelSub.classList.contains('oculta')) {
        panelSub.classList.add('oculta');
    }
    gestionarFlechas('panelGrupos');
    gestionarFlechas('panelSubcategorias');
    ajustarPosicionesPaneles();
}



function ajustarPosicionesPaneles() {
  const panelGrupos = document.getElementById('panelGrupos');
  const panelSub = document.getElementById('panelSubcategorias');
  const barraNav = document.querySelector('.barra-navegacion');

  if (!panelGrupos || !panelSub) return;

  let alturaBarra = barraNav ? barraNav.offsetHeight : 0;

  let alturaGrupos = 0;
  if (!panelGrupos.classList.contains('oculta')) {
    alturaGrupos = panelGrupos.offsetHeight;
  }

  const contenedorGrupos = panelGrupos.parentElement;
  const flechaIzqGrupos = contenedorGrupos.querySelector('.flecha-izq');
  const flechaDerGrupos = contenedorGrupos.querySelector('.flecha-der');

  if (!panelGrupos.classList.contains('oculta')) {
    panelGrupos.style.top = alturaBarra + 'px';
    panelGrupos.style.position = 'fixed';
    panelGrupos.style.left = '0';
    panelGrupos.style.right = '0';

    if (flechaIzqGrupos) {
      flechaIzqGrupos.style.top = (alturaBarra + 2) + 'px';
      flechaIzqGrupos.style.display = 'flex'; 
    }
    if (flechaDerGrupos) {
      flechaDerGrupos.style.top = (alturaBarra + 2) + 'px';
      flechaDerGrupos.style.display = 'flex';
    }
  } else {
    if (flechaIzqGrupos) flechaIzqGrupos.style.display = 'none';
    if (flechaDerGrupos) flechaDerGrupos.style.display = 'none';
  }

  const contenedorSub = panelSub.parentElement;
  const flechaIzqSub = contenedorSub.querySelector('.flecha-izq');
  const flechaDerSub = contenedorSub.querySelector('.flecha-der');

  if (!panelSub.classList.contains('oculta')) {
    const margenAdicional = 19;
    const desplazamientoArriba = -20;
    const topCalc = alturaBarra + alturaGrupos + margenAdicional + desplazamientoArriba;

    panelSub.style.top = topCalc + 'px';
    panelSub.style.position = 'fixed';
    panelSub.style.left = '0';
    panelSub.style.right = '0';

    if (flechaIzqSub) {
      flechaIzqSub.style.top = (topCalc + 2) + 'px';
      flechaIzqSub.style.display = 'flex';
    }
    if (flechaDerSub) {
      flechaDerSub.style.top = (topCalc + 2) + 'px';
      flechaDerSub.style.display = 'flex';
    }
  } else {
    if (flechaIzqSub) flechaIzqSub.style.display = 'none';
    if (flechaDerSub) flechaDerSub.style.display = 'none';
  }

  gestionarFlechas('panelGrupos');
  gestionarFlechas('panelSubcategorias');
}


function getItemsPorPagina() {
    if (isMobile && window.modoAdmin) return 4; 
    if (isMobile) return 5; 
    return 12; 
}


async function calcularEnvioPaso() {
  const emailVendedor = window.cliente?.email;
  if (!emailVendedor) {
    alert("No se pudo identificar al vendedor");
    return;
  }

  const codigoPostal = document.getElementById('codigo_postal').value.trim();
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

  const btnCalcular = document.getElementById('btnCalcularEnvioPaso');
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
      window.costoEnvio = data.costo;
      document.getElementById("costoEnvioMostrado").innerHTML = `<strong>Envío:</strong> $${data.costo.toFixed(2)}`;
      actualizarCarritoConEnvio(); 
      envioCalculado = true;
      document.getElementById('btnSiguienteDatos').style.display = 'block';
    } else {
      alert("No se pudo calcular el envío: " + (data.error || "Error desconocido"));
      window.costoEnvio = 0;
      document.getElementById("costoEnvioMostrado").innerHTML = "";
      envioCalculado = false;
    }
  } catch (err) {
    console.error(err);
    alert("Error al calcular envío. Verifica tu conexión.");
    window.costoEnvio = 0;
    envioCalculado = false;
  } finally {
    if (btnCalcular) {
      btnCalcular.disabled = false;
      btnCalcular.textContent = 'Calcular envío';
    }
  }
}



function irAContacto() {
  const contacto = document.getElementById('ubicacion');
  if (contacto) contacto.scrollIntoView({ behavior: 'smooth' });
}
window.irAContacto = irAContacto; 


function loadVisibleImagesFirst() {
  const lazyImages = document.querySelectorAll('.card-giratoria img[data-src]');
  if (lazyImages.length === 0) return;
  const viewportHeight = window.innerHeight;
  let loadedCount = 0;
  lazyImages.forEach(img => {
    const rect = img.getBoundingClientRect();
    if (rect.top < viewportHeight + 300 && rect.bottom > -100 && img.dataset.src) {
      img.src = img.dataset.src;
      img.onload = () => {
        img.removeAttribute('data-src');
        img.style.opacity = '0';
        setTimeout(() => {
          img.style.opacity = '1';
          img.style.transition = 'opacity 0.3s ease';
        }, 10);
      };
      loadedCount++;
      if (window.innerWidth < 768 && loadedCount >= 3) return;
    }
  });
  if (loadedCount > 0) console.log(`🖼️ Lazy: Cargadas ${loadedCount} imágenes en cards`);
}


function setupEnhancedLazyLoading() {
  const lazyImages = document.querySelectorAll('.card-giratoria img[data-src]');
  if (lazyImages.length === 0) return;
  if (lazyImages.length <= 8) {
    lazyImages.forEach(img => {
      if (img.dataset.src) {
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
      }
    });
    return;
  }
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            const tempImg = new Image();
            tempImg.src = img.dataset.src;
            tempImg.onload = () => {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
              img.style.opacity = '1';
            };
          }
          observer.unobserve(img);
        }
      });
    }, { rootMargin: window.innerWidth < 768 ? '200px' : '100px', threshold: 0.01 });
    lazyImages.forEach(img => observer.observe(img));
  }
}



function cargarMercadoPagoJS() {
  return new Promise((resolve, reject) => {
    if (window.mercadoPagoCargado) return resolve();

    const cargar = () => {
      const script = document.createElement('script');
      script.src = 'static/js/mercadopago.js';
      script.async = true; 
      script.onload = async () => {
        window.mercadoPagoCargado = true;
        resolve();
      };
      script.onerror = reject;
      document.head.appendChild(script);
    };

    if ('requestIdleCallback' in window) {
      requestIdleCallback(cargar, { timeout: 2000 });
    } else {
      setTimeout(cargar, 1000); 
    }
  });
}
let pagando = false;


document.addEventListener('DOMContentLoaded', () => {
  // ============================================================
  // 1. CONFIGURACIÓN DEL CARRITO Y ENVÍOS
  // ============================================================
  const btnContinuar = document.getElementById('btnContinuar');
  if (btnContinuar) btnContinuar.addEventListener('click', mostrarPasoDireccion);

  const btnSiguienteDatos = document.getElementById('btnSiguienteDatos');
  if (btnSiguienteDatos) btnSiguienteDatos.addEventListener('click', mostrarPasoDatos);

  const btnVolverCarrito = document.getElementById('btnVolverCarrito');
  if (btnVolverCarrito) btnVolverCarrito.addEventListener('click', volverAlCarrito);

  const btnVolverDireccion = document.getElementById('btnVolverDireccion');
  if (btnVolverDireccion) btnVolverDireccion.addEventListener('click', volverADireccion);

  const btnSinEnvio = document.getElementById('btnSinEnvio');
  if (btnSinEnvio) btnSinEnvio.addEventListener('click', continuarSinEnvio);

  const btnCalcular = document.getElementById('btnCalcularEnvioPaso');
  if (btnCalcular) {
    btnCalcular.addEventListener('click', async () => {
      await calcularEnvioPaso();
    });
  }

  const btnPagar = document.getElementById('btnPagarFinal');
  if (btnPagar) {
    btnPagar.addEventListener('click', () => {
      if (typeof window.pagarTodoJunto === 'function') {
        window.pagarTodoJunto();
      } else {
        alert("El módulo de pagos aún no está listo. Intentá de nuevo en unos segundos.");
      }
    });
  }

  // ============================================================
  // 2. CARDS, LAZY LOADING, EVENTOS TÁCTILES Y SCROLL
  // ============================================================
  document.querySelectorAll('.card-giratoria').forEach(card => {
    card.addEventListener('touchstart', (e) => {
      e.preventDefault();
      card.style.transform = 'scale(0.98)';
    }, { passive: false });
    card.addEventListener('touchend', () => {
      card.style.transform = '';
    });

    let touchStartTime, touchStartX, touchStartY;
    card.addEventListener('touchstart', (e) => {
      touchStartTime = Date.now();
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
    }, { passive: true });
    card.addEventListener('touchend', (e) => {
      const touchDuration = Date.now() - touchStartTime;
      const deltaX = Math.abs(e.changedTouches[0].clientX - touchStartX);
      const deltaY = Math.abs(e.changedTouches[0].clientY - touchStartY);
      if (touchDuration < 300 && deltaX < 10 && deltaY < 10) {
        const girarBtn = card.querySelector('.btn-girar');
        if (girarBtn) girarBtn.click();
      }
    });
  });

  const toggleCarrito = document.getElementById('toggleCarrito');
  if (toggleCarrito) {
    toggleCarrito.addEventListener('click', cargarMercadoPagoJS);
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          cargarMercadoPagoJS();
          observer.disconnect();
        }
      }, { rootMargin: '300px' });
      observer.observe(toggleCarrito);
    }
  }
  if (window.modoAdmin) cargarMercadoPagoJS();

  setTimeout(loadVisibleImagesFirst, 300);
  setTimeout(setupEnhancedLazyLoading, 800);

  window.addEventListener('scroll', () => {
    if (!isScrolling) {
      isScrolling = true;
      loadVisibleImagesFirst();
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        loadVisibleImagesFirst();
        isScrolling = false;
      }, 150);
    }
    const btnArriba = document.getElementById('volverArriba');
    if (btnArriba) {
      btnArriba.style.display = window.scrollY > 300 ? 'block' : 'none';
    }
    const btnLogin = document.getElementById('loginToggleBtn');
    if (btnLogin && !window.modoAdmin) {
      const isBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 100;
      btnLogin.style.display = isBottom ? 'block' : 'none';
    }
  }, { passive: true });

  window.addEventListener("load", ajustarPosicionesPaneles);
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => ajustarPosicionesPaneles(), 150);
  });

  // ============================================================
  // 3. EVENTOS DE CLICK GLOBAL (cerrar carrito/paneles y girar cards)
  // ============================================================
  document.addEventListener('click', (e) => {
    // Cerrar carrito si se clic fuera
    const carritoDiv = document.getElementById("carrito");
    const toggleBtn = document.getElementById("toggleCarrito");
    if (carritoDiv && toggleBtn) {
      const visible = carritoDiv.style.display === "block";
      const clicFueraCarrito = !carritoDiv.contains(e.target) && !toggleBtn.contains(e.target);
      if (visible && clicFueraCarrito) carritoDiv.style.display = "none";
    }

    // Cerrar paneles de grupos/subcategorías si se clic fuera
    const panelGrupos = document.getElementById("panelGrupos");
    const panelSub = document.getElementById("panelSubcategorias");
    if (panelGrupos && panelSub) {
      const esClickDentroGrupos = panelGrupos.contains(e.target);
      const esClickDentroSub = panelSub.contains(e.target);
      const esBotonGrupo = e.target.classList.contains("btn-grupo") || e.target.closest('.btn-grupo');
      const esBotonSubgrupo = e.target.classList.contains("btn-subgrupo") || e.target.closest('.btn-subgrupo');
      const esBotonNavegacion = !!e.target.closest(".barra-navegacion");

      if (!esClickDentroGrupos && !esClickDentroSub && 
          !esBotonGrupo && !esBotonSubgrupo && !esBotonNavegacion) {
        setTimeout(() => {
          panelGrupos.classList.add("oculta");
          panelSub.classList.add("oculta");
          gestionarFlechas('panelGrupos');
          gestionarFlechas('panelSubcategorias');
        }, 300);
      }
    }

    // Girar cards al hacer clic en los botones correspondientes
    if (e.target.classList.contains('btn-girar') || e.target.classList.contains('btn-reversa')) {
      const card = e.target.closest('.card-giratoria');
      if (card) {
        setTimeout(() => {
          card.querySelectorAll('img[data-src]').forEach(img => {
            if (img.dataset.src) {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
            }
          });
        }, 100);
      }
    }
  });

  // ============================================================
  // 4. SELECTOR DE ORDEN POR PRECIO
  // ============================================================
  const ordenSelect = document.getElementById("ordenPrecio");
  if (ordenSelect) {
    ordenSelect.addEventListener("change", (e) => {
      if (!window.currentGrupo) return;
      let productosFiltrados = window.todosLosProductos.filter(p =>
        p.grupo?.toLowerCase() === window.currentGrupo
      );
      if (window.currentSub) {
        productosFiltrados = productosFiltrados.filter(p =>
          p.subgrupo?.toLowerCase() === window.currentSub
        );
      }
      productosFiltrados.sort((a, b) => {
        const pa = parseFloat(a.precio) || 0;
        const pb = parseFloat(b.precio) || 0;
        return e.target.value === "asc" ? pa - pb : pb - pa;
      });
      paginaActual = 1;
      productosFiltradosActuales = productosFiltrados;
      renderPagina(1, productosFiltrados);
      renderPaginacion(productosFiltrados);
    });
  }

  // ============================================================
  // 5. BOTÓN VOLVER ARRIBA
  // ============================================================
  const volverArribaBtn = document.getElementById('volverArriba');
  if (volverArribaBtn) {
    volverArribaBtn.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ============================================================
  // 6. BOTÓN LOGIN ADMIN (muestra/oculta formulario)
  // ============================================================
  const loginToggleBtn = document.getElementById('loginToggleBtn');
  if (loginToggleBtn) {
    loginToggleBtn.onclick = () => {
      const form = document.getElementById('loginFloatingForm');
      if (form) {
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
        if (form.style.display === 'block' && !window.adminScriptCargado) {
          const script = document.createElement('script');
          script.src = 'static/js/admin.js';
          script.onload = () => { window.adminScriptCargado = true; };
          document.head.appendChild(script);
        }
      }
    };
  }

  // ============================================================
  // 7. EVENTO CLICK EN EL LOGO (animación)
  // ============================================================
  const logoElement = document.querySelector('.logo');
  if (logoElement) {
    logoElement.addEventListener('click', function() {
      const logo = this;
      logo.style.pointerEvents = 'none';
      logo.style.transition = 'transform 0.8s ease, opacity 0.4s ease';
      logo.style.transform = 'rotateY(360deg)';
      logo.style.opacity = '0.7';
      
      const mensaje = document.createElement('div');
      mensaje.textContent = 'Gracias por la visita! ❤️';
      mensaje.style.position = 'fixed';
      mensaje.style.top = '50%';
      mensaje.style.left = '50%';
      mensaje.style.transform = 'translate(-50%, -50%) scale(0.8)';
      mensaje.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
      mensaje.style.color = 'white';
      mensaje.style.padding = '15px 25px';
      mensaje.style.borderRadius = '20px';
      mensaje.style.fontFamily = "'Raleway', sans-serif";
      mensaje.style.fontSize = '1.2rem';
      mensaje.style.fontWeight = 'bold';
      mensaje.style.zIndex = '999999';
      mensaje.style.opacity = '0';
      mensaje.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      mensaje.style.boxShadow = '0 0 30px rgba(255, 255, 255, 0.7), 0 0 60px rgba(139, 92, 246, 0.5)';
      mensaje.style.backdropFilter = 'blur(10px)';
      mensaje.style.border = '2px solid rgba(255, 255, 255, 0.3)';
      document.body.appendChild(mensaje);
      
      setTimeout(() => {
        mensaje.style.opacity = '1';
        mensaje.style.transform = 'translate(-50%, -50%) scale(1.1)';
        setTimeout(() => {
          mensaje.style.transform = 'translate(-50%, -50%) scale(1)';
          setTimeout(() => {
            mensaje.style.opacity = '0';
            mensaje.style.transform = 'translate(-50%, -50%) scale(0.8)';
            setTimeout(() => {
              mensaje.remove();
            }, 500);
            logo.style.transform = 'rotateY(0deg)';
            logo.style.opacity = '1';
            setTimeout(() => {
              logo.style.pointerEvents = 'auto';
              logo.style.transition = '';
            }, 800);
          }, 1500);
        }, 300);
      }, 400);
    });
  }

  // ============================================================
  // 8. CAMBIO DE TALLE (actualizar stock)
  // ============================================================
  document.addEventListener('change', (e) => {
    if (e.target.id && e.target.id.startsWith('talle_')) {
      const idProducto = e.target.id.replace('talle_', '');
      const talleSeleccionado = e.target.value;
      if (talleSeleccionado) actualizarStockPorTalle(idProducto, talleSeleccionado);
    }
  });
});
