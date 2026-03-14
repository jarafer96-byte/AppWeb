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
window.stockPorTalleData = {};
let urlProductos = `https://mpagina.onrender.com/api/productos?usuario=${encodeURIComponent(email)}`;

if (window.modoAdmin && window.tokenAdmin) {
  urlProductos += `&token=${encodeURIComponent(window.tokenAdmin)}`;
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
    console.log("🌐 Productos recibidos y ordenados:", window.todosLosProductos.length);

    setTimeout(() => {
      const gruposUnicos = [...new Set(productosOrdenados.map(p => p.grupo).filter(Boolean))];
      const subgruposUnicos = [...new Set(productosOrdenados.map(p => p.subgrupo).filter(Boolean))];
      
      const datalistGrupos = document.getElementById('grupos-sugeridos');
      if (datalistGrupos && gruposUnicos.length > 0) {
        datalistGrupos.innerHTML = '';
        gruposUnicos.forEach(grupo => {
          const option = document.createElement('option');
          option.value = grupo;
          datalistGrupos.appendChild(option);
        });
        console.log(`✅ ${gruposUnicos.length} grupos para sugerencias`);
      }
      
      const datalistSubgrupos = document.getElementById('subgrupos-sugeridos');
      if (datalistSubgrupos && subgruposUnicos.length > 0) {
        datalistSubgrupos.innerHTML = '';
        subgruposUnicos.forEach(subgrupo => {
          const option = document.createElement('option');
          option.value = subgrupo;
          datalistSubgrupos.appendChild(option);
        });
        console.log(`✅ ${subgruposUnicos.length} subgrupos para sugerencias`);
      }
    }, 100);

    const cont = document.getElementById("productos");
    const contGrupos = document.getElementById("panelGrupos");
    const contSub = document.getElementById("panelSubcategorias");

    if (!cont) {
      console.warn("⚠️ No existe #productos en el DOM");
      return;
    }
    if (!contGrupos || !contSub) {
      console.warn("⚠️ Faltan paneles #panelGrupos o #panelSubcategorias en el DOM");
    }

    const grupos = [...new Set(window.todosLosProductos.map(p => p.grupo).filter(Boolean))];
    console.log("📂 Grupos detectados:", grupos);

    if (contGrupos) {
      contGrupos.innerHTML = ""; 
      grupos.forEach(g => {
        const btn = document.createElement("button");
        btn.className = "btn-grupo";
        btn.textContent = g;
        btn.addEventListener("click", (e) => {
          console.log("🟢 Click en botón grupo:", g);
          mostrarGrupo(g, e);
        });
        contGrupos.appendChild(btn);
        console.log("➕ Botón grupo creado:", g);
      });
    }

    const primerGrupo = grupos[0];
    const subgruposPrimer = [...new Set(window.todosLosProductos
      .filter(p => p.grupo === primerGrupo)
      .map(p => p.subgrupo).filter(Boolean))];

    console.log("🎯 Primer grupo:", primerGrupo);
    console.log("📂 Subgrupos del primer grupo:", subgruposPrimer);

    if (primerGrupo) {
      if (subgruposPrimer.length > 0) {
        console.log("➡️ Render inicial con subgrupo:", subgruposPrimer[0]);
        filtrarSubcategoria(primerGrupo, subgruposPrimer[0]);
      } else {
        console.log("➡️ Render inicial con grupo completo");
        mostrarGrupo(primerGrupo, null, true);
      }
    }

    console.log("✅ Render inicial completado");
  })
  .catch(err => {
    cargaCompleta = true;
    console.error("💥 Error cargando productos:", err);
    const cont = document.getElementById("productos");
    if (cont) cont.innerHTML = "<p class='text-danger text-center'>Error al cargar productos. Intenta de nuevo.</p>";
  });

function renderPagina(pagina, productos) {
  const cont = document.getElementById("productos");
  if (!cont) return;

  const itemsPorPagina = getItemsPorPagina();

  if (!productos || productos.length === 0) {
    cont.innerHTML = '';
    for (let i = 0; i < itemsPorPagina; i++) {
      cont.appendChild(crearSkeletonCard());
    }
    return;
  }

  const inicio = (pagina - 1) * itemsPorPagina;
  const fin = Math.min(inicio + itemsPorPagina, productos.length);
  const productosPagina = productos.slice(inicio, fin);

  cont.innerHTML = '';
  productosPagina.forEach((p, index) => {
    const esLCP = (pagina === 1 && index === 0);
    cont.appendChild(renderProducto(p, esLCP));
  });
}

function crearSkeletonCard() {
  const div = document.createElement('div');
  div.className = 'col-lg-4 col-md-6 col-sm-12 mb-4';
  div.innerHTML = `
    <div class="skeleton-card">
      <div class="skeleton-image"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line short"></div>
      <div class="skeleton-line medium"></div>
    </div>
  `;
  return div;
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
    };
    pagDiv.appendChild(btn);
  }
}

function renderProducto(p, esLCP = false) {
  const card = document.createElement("div");
  card.className = "col-lg-4 col-md-6 col-sm-12 mb-4 fade-reorder card-producto";
  card.dataset.id = p.id_base;
  card.dataset.precio = p.precio;

  const precioActual = parseFloat(p.precio) || 0;
  const precioAnterior = parseFloat(p.precio_anterior) || 0;

  const esOferta = precioAnterior > 0 && precioAnterior > precioActual;
  const descuentoPorcentaje = esOferta ? 
    Math.round(((precioAnterior - precioActual) / precioAnterior) * 100) : 0;

  if (!esOferta && window.todosLosProductos) {
    const productoCompleto = window.todosLosProductos.find(prod => prod.id_base === p.id_base);
    if (productoCompleto) {
      if (productoCompleto.precio_anterior && productoCompleto.precio_anterior > precioActual) {
        precioAnterior = parseFloat(productoCompleto.precio_anterior) || 0;
        esOferta = precioAnterior > 0 && precioAnterior > precioActual;
      }
    }
  }
  
  const tieneStockPorTalle = p.stock_por_talle && Object.keys(p.stock_por_talle).length > 0;
  
  let stockData = {};
  let opcionesTalles = "";
  let talleInicial = "";
  let stockInicial = 0;
  
  if (tieneStockPorTalle) {
    stockData = p.stock_por_talle;
    window[`stock_por_talle_${p.id_base}`] = stockData;

    const tallesDisponibles = Object.keys(stockData);
    
    tallesDisponibles.forEach(talle => {
      const stock = stockData[talle] || 0;
      
      const opcion = stock > 0 ? 
        `<option value="${talle}">${talle} (${stock} disponible${stock > 1 ? 's' : ''})</option>` :
        `<option value="${talle}" disabled>${talle} (Agotado)</option>`;
      opcionesTalles += opcion;
    
      if (stockInicial === 0 && stock > 0) {
        stockInicial = stock;
        talleInicial = talle;
      }
    });

    if (stockInicial === 0 && tallesDisponibles.length > 0) {
      talleInicial = tallesDisponibles[0];
      stockInicial = stockData[talleInicial] || 0;
    }
  } else {
    let stockGeneral = 0;
    if (p.stock_por_talle && p.stock_por_talle["unico"] !== undefined) {
        stockGeneral = p.stock_por_talle["unico"];
    } else if (p.stock) {
        stockGeneral = p.stock;
    }
    stockData = { "unico": stockGeneral };
    window[`stock_por_talle_${p.id_base}`] = stockData;
    stockInicial = stockGeneral;
  }
  
  const mostrarStock = stockInicial > 0 ? stockInicial : "Sin stock";
  const claseStock = stockInicial > 0 ? "" : "text-danger";

  const nombreEscapado = p.nombre.replace(/'/g, "\\'").replace(/"/g, '\\"');
  const descripcionEscapada = (p.descripcion || "").replace(/'/g, "\\'").replace(/"/g, '\\"');
  const imagenGrande = p.imagen_url || '/static/img/fallback.webp';
  const imagenGrandeEscapada = imagenGrande.replace(/'/g, "\\'");
  const grupoEscapado = (p.grupo || "").replace(/'/g, "\\'");
  const subgrupoEscapado = (p.subgrupo || "").replace(/'/g, "\\'");
  const imagenCard = getVersionUrl(imagenGrande, '180');
  
  const fotosAdicionalesSeguras = (p.fotos_adicionales || []).map(foto => 
    foto.replace(/'/g, "\\'").replace(/"/g, '\\"')
  );
  
  const onclickAgregar = `agregarAlCarritoDOM('${nombreEscapado}', 'precio_${p.id_base}', 'cantidad_${p.id_base}', '${p.id_base}', '${grupoEscapado}', '${subgrupoEscapado}', '${imagenGrandeEscapada}')`;
  
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

  const fotosAdicionalesHTML = fotosAdicionalesSeguras.length > 0 ? `
    <div class="fotos-adicionales mt-2">
      <div class="d-flex flex-wrap mt-1" style="gap: 3px;">
        ${fotosAdicionalesSeguras.map((foto, idx) => {
            const miniatura = getVersionUrl(foto, '58');
            return `
                <img src="${miniatura}" 
                     alt="Foto ${idx+1}" 
                     style="width: 40px; height: 40px; object-fit: cover; border-radius: 3px; cursor: pointer;"
                     onclick="openModal('${foto}')">
            `;
        }).join('')}
      </div>
    </div>
  ` : '';
  
  let imgAttributes = `src="${imagenCard}"`;
  if (!esLCP) {
      imgAttributes += ` data-src="${imagenCard}" loading="lazy"`;
  } else {
      imgAttributes += ` loading="eager" fetchpriority="high"`;
  }
  
  card.innerHTML = `
  <div class="card-giratoria">
    <div class="card-contenedor">
      <!-- FRENTE (COMPLETO) -->
      <div class="card-front">
        ${esOferta ? `
          <div class="oferta-badge" style="
            position: absolute;
            top: 10px;
            left: 10px;
            background: linear-gradient(45deg, #ff4757, #ff3838);
            color: white;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: bold;
            z-index: 5;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
            pointer-events: none;
            animation: pulseOferta 2s infinite;
            transform-style: preserve-3d;
          ">
            🔥 OFERTA -${descuentoPorcentaje}%
          </div>
        ` : ''}
        
        <!-- Botón para girar -->
        <button class="btn-girar" onclick="girarCard(this)">
          🔄
        </button>
        
        <img ${imgAttributes}
             alt="${p.nombre}"
             width="300"
             height="180"
             style="width:100%; height:180px; object-fit:contain; border-radius:4px; cursor:pointer; opacity:0;"
             class="lazy-image"
             onload="this.style.opacity='1'"
             onclick="openModal('${imagenGrandeEscapada}')">
        <div class="card-body">
          <h5 class="card-title" style="font-size: 1.1rem !important;">${p.nombre}</h5>
          
          <p class="mb-2">
            <strong>Precio:</strong> 
            ${esOferta ? `
              <span style="text-decoration: line-through; color: #999; font-size: 0.9rem; margin-right: 5px;">
                $${precioAnterior.toFixed(2)}
              </span>
            ` : ''}
            $<span id="precio_${p.id_base}" style="${esOferta ? 'color: #ff4757; font-weight: bold;' : ''}">${p.precio}</span>
            ${esOferta ? `<small style="color: #20c997; font-weight: bold; margin-left: 5px;">Ahorras $${(precioAnterior - precioActual).toFixed(2)}</small>` : ''}
          </p>
          
          ${Object.keys(stockData).length > 0 && Object.keys(stockData)[0] !== "unico" ? `
  <div class="mb-2 d-flex align-items-center gap-2">
    <label class="mb-0"><strong>Talle:</strong></label>
    <select id="talle_${p.id_base}" class="form-select form-select-sm w-auto"
            onchange="actualizarStockPorTalle('${p.id_base}', this.value)"
            style="min-width: 160px; max-width: 180px;"
            aria-label="Seleccionar talle para ${p.nombre}">
      <option value="">-</option>
      ${opcionesTalles}
    </select>
  </div>
` : ""}
          
          <div class="mt-3 d-flex align-items-center gap-2">
            <input type="number" min="1" max="${stockInicial > 0 ? stockInicial : 1}" value="1"
                   id="cantidad_${p.id_base}"
                   class="form-control form-control-sm" style="width: 70px;"
                   ${stockInicial <= 0 ? "disabled" : ""}
                   aria-label="Cantidad de ${p.nombre}">
            
            <button type="button" class="btn btn-secondary btn-sm" id="btn_agregar_${p.id_base}"
              onclick="${onclickAgregar}"
              ${stockInicial <= 0 ? "disabled style='opacity:0.5'" : ""}>
              ${stockInicial > 0 ? "Agregar al carrito" : "❌ Sin stock"}
            </button>
          </div>
          
          ${fotosAdicionalesHTML}
          
          ${whatsappUrl ? `
            <div class="mt-3">
              <a href="${whatsappUrl}" class="btn btn-whatsapp btn-sm w-100 d-flex align-items-center justify-content-center gap-2" target="_blank" style="background-color: #0c6909; color: white;">
                <img src="/static/img/whatsapp.webp" alt="WhatsApp" style="width: 20px; height: 20px;">
                Consultar
              </a>
            </div>
          ` : ""}
        </div>
      </div>
      
      <!-- REVERSO (SOLO DESCRIPCIÓN) -->
      <div class="card-back" style="display: flex; flex-direction: column; height: 100%;">
        <!-- Botón para volver al frente (arriba a la derecha) -->
        <button class="btn-reversa" onclick="girarCard(this)" style="position: absolute; top: 10px; right: 10px;">
          ↩️
        </button>
        
        <!-- ÁREA DE DESCRIPCIÓN (OCUPA TODO EL ESPACIO DISPONIBLE) -->
        <div class="descripcion-area" style="
          flex: 1;
          padding: 80px 80px 80px 80px;
          overflow-y: auto;
          text-align: center;
          flex-direction: column;
          justify-content: center;
          scrollbar-width: none;
          -ms-overflow-style: none;
        ">
          <div class="descripcion-area::-webkit-scrollbar {
            display: none;
          }">
            ${p.descripcion ? `
              <div style="
                font-size: 1rem;
                line-height: 1.5;
                color: #f8f9fa;
                white-space: pre-line;
                max-height: 100%;
              ">
                ${p.descripcion}
              </div>
            ` : `
              <div style="
                font-size: 1rem;
                color: #adb5bd;
                font-style: italic;
              ">
                Este producto no tiene descripción adicional.
              </div>
            `}
          </div>
        </div>
        
        <!-- SECCIÓN INFERIOR (FUERA DEL ÁREA DE DESCRIPCIÓN) -->
        <div class="card-back-footer" style="
          padding: 15px;
          border-top: 1px solid rgba(255,255,255,0.1);
          background: rgba(0,0,0,0.2);
        ">
          ${Object.keys(stockData).length > 0 && Object.keys(stockData)[0] !== "unico" ? `
            <div class="mb-2" style="
              background: rgba(255,255,255,0.05);
              padding: 8px 12px;
              border-radius: 6px;
              font-size: 0.9rem;
              color: #dee2e6;
            ">
              <strong>Talles:</strong> ${Object.keys(stockData).join(", ")}
            </div>
          ` : ""}
          
          <div class="mt-2">
            <button class="btn btn-secondary btn-sm w-100" onclick="girarCard(this)">
              🔄 Volver al frente
            </button>
          </div>
          
          ${window.modoAdmin ? `
  <div class="mt-2 d-flex gap-2">
    <button type="button" class="btn btn-info btn-sm flex-fill" style="background-color: azure;" onclick="duplicarProductoDesdeCard('${p.id_base}')">
      📋 Duplicar
    </button>
    <button type="button" class="btn btn-warning btn-sm flex-fill"
      onclick="editarProductoDesdeCard('${p.id_base}')">
      ✏️ Editar
    </button>
    <button type="button" class="btn btn-danger btn-sm flex-fill"
      onclick="eliminarProducto('${p.id_base}')">
      🗑️ Eliminar
    </button>
  </div>
` : ""}
        </div>
      </div>
    </div>
  </div>
`;

  if (talleInicial) {
    setTimeout(() => {
      const talleSelect = document.getElementById(`talle_${p.id_base}`);
      if (talleSelect) {
        talleSelect.value = talleInicial;
        actualizarStockPorTalle(p.id_base, talleInicial);
      }
    }, 100);
  }

  requestAnimationFrame(() => card.classList.add("show"));
  setTimeout(() => card.classList.remove("fade-reorder"), 50);

  return card;
}

(function() {
  if (!document.getElementById('oferta-animacion-css')) {
    const style = document.createElement('style');
    style.id = 'oferta-animacion-css';
    style.textContent = `
      @keyframes pulseOferta {
        0%, 100% { 
          transform: scale(1); 
          box-shadow: 0 2px 5px rgba(0,0,0,0.3); 
        }
        50% { 
          transform: scale(1.05); 
          box-shadow: 0 4px 10px rgba(255, 71, 87, 0.5); 
        }
      }
      
      /* Estilo para productos en oferta */
      .card-producto.oferta {
        border-left: 4px solid #ff4757;
      }
      
      /* Destacar precio en oferta */
      .precio-oferta {
        color: #ff4757 !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
      }
      
      .precio-anterior-tachado {
        text-decoration: line-through;
        color: #999;
        font-size: 0.9rem;
        margin-right: 5px;
      }
      
      /* Para ofertas especiales (descuento > 20%) */
      .oferta-especial {
        background: linear-gradient(45deg, #ff9500, #ff5e3a) !important;
      }
    `;
    document.head.appendChild(style);
    console.log("✅ Animación CSS de ofertas agregada");
  }
})();

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
    console.log("✅ Carrito configurado inmediatamente");
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
    if (item.talle) descripcion += ` (Talle: ${item.talle})`;
    if (item.color) descripcion += ` (Color: ${item.color})`;

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

function actualizarStockPorTalle(idProducto, talleSeleccionado) {
  console.log(`📊 [actualizarStockPorTalle] id: ${idProducto}, talle: ${talleSeleccionado}`);
  
  const cantidadInput = document.getElementById(`cantidad_${idProducto}`);
  const agregarBtn = document.getElementById(`btn_agregar_${idProducto}`);
  
  if (!cantidadInput || !agregarBtn) {
    console.warn("⚠️ Elementos no encontrados");
    return;
  }

  let stockDisponible = 0;
  const stockPorTalle = window[`stock_por_talle_${idProducto}`];
  
  if (stockPorTalle && stockPorTalle[talleSeleccionado] !== undefined) {
    stockDisponible = stockPorTalle[talleSeleccionado];
    console.log(`✅ Stock obtenido: ${stockDisponible} para talle ${talleSeleccionado}`);
  } else {
    console.warn(`⚠️ Talle ${talleSeleccionado} no encontrado en stock_por_talle`);
    stockDisponible = 0;
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
    cantidadInput.value = "0";
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


function agregarAlCarritoDOM(nombre, idPrecioSpan, idCantidad, id_base, grupo = "", subgrupo = "", imagenUrl = "") {
  const cantidadInput = document.getElementById(idCantidad);
  const precioSpan = document.getElementById(idPrecioSpan);
  const talleSelect = document.getElementById(`talle_${id_base}`);
  
  if (!cantidadInput || !precioSpan) {
    alert("❌ Error: No se pudieron obtener los datos del producto");
    return;
  }
  
  const talleElegido = talleSelect?.value || "unico";
  
  let stockDisponible = 0;
  const stockPorTalle = window[`stock_por_talle_${id_base}`];
  
  if (stockPorTalle) {
    stockDisponible = stockPorTalle[talleElegido] || 0;
  }
  
  if (stockDisponible <= 0) {
    alert("❌ No hay stock disponible" + (talleElegido !== "unico" ? ` para el talle ${talleElegido}` : ""));
    return;
  }
  
  const cantidad = parseInt(cantidadInput.value) || 1;
  
  if (cantidad > stockDisponible) {
    alert(`❌ Solo hay ${stockDisponible} unidades disponibles${talleElegido !== "unico" ? ` para el talle ${talleElegido}` : ""}`);
    cantidadInput.value = stockDisponible;
    return;
  }
  
  const precio = parseFloat(precioSpan.textContent.replace("$", "").replace(",", "")) || 0;
  
  // Buscar en window.carrito
  const existente = window.carrito.find(item => 
    item.id_base === id_base && 
    item.talle === talleElegido
  );
  
  if (existente) {
    const nuevoTotal = existente.cantidad + cantidad;
    
    if (nuevoTotal > stockDisponible) {
      alert(`❌ No puedes llevar más de ${stockDisponible} unidades${talleElegido !== "unico" ? ` del talle ${talleElegido}` : ""}`);
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
      grupo, 
      subgrupo, 
      imagen_url: imagenUrl   // ← ahora imagenUrl está definida
    };
    window.carrito.push(nuevoItem);
  }
  
  actualizarCarrito(true);

  const contadorSpan = document.getElementById('carrito-contador');
  if (contadorSpan) {
    contadorSpan.classList.add('pop-animation');
    setTimeout(() => contadorSpan.classList.remove('pop-animation'), 400);
  }

  const toggleBtn = document.getElementById('toggleCarrito');
  if (toggleBtn) {
    toggleBtn.classList.add('carrito-shake');
    setTimeout(() => toggleBtn.classList.remove('carrito-shake'), 300);
  }

  mostrarToast(`✅ ${nombre} agregado al carrito`);
}

function vaciarCarrito() {
    window.carrito = [];
    actualizarCarrito();
    ocultarFormulario(); 
}

function eliminarDelCarrito(id_base, talle, event) {
  if (event?.stopPropagation) event.stopPropagation();

  console.log("[CARRITO] ❌ Eliminando:", { id_base, talle });

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

function actualizarUIStock(idProducto, stockDisponible, talleSeleccionado) {
  const stockSpan = document.getElementById(`stock_${idProducto}`);
  const cantidadInput = document.getElementById(`cantidad_${idProducto}`);
  const agregarBtn = document.getElementById(`btn_agregar_${idProducto}`);
  
  stockSpan.textContent = stockDisponible > 0 ? stockDisponible : "Sin stock";
  
  if (stockDisponible > 0) {
    stockSpan.classList.remove("text-danger");
    stockSpan.classList.add("text-success");
    setTimeout(() => stockSpan.classList.remove("text-success"), 1000);
  } else {
    stockSpan.classList.remove("text-success");
    stockSpan.classList.add("text-danger");
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
    cantidadInput.value = "0";
    
    agregarBtn.disabled = true;
    agregarBtn.style.opacity = "0.5";
    agregarBtn.textContent = "Sin stock";
  }
  
  console.log(`✅ Stock actualizado: Talle ${talleSeleccionado} → ${stockDisponible} unidades`);
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

function mostrarFormulario() {
    console.log("📝 Mostrando formulario de datos del cliente");

    const datosCliente = document.getElementById('datosCliente');
    if (datosCliente) {
        datosCliente.style.display = 'block';
    }

    const btnContinuar = document.getElementById('btnContinuar');
    if (btnContinuar) {
        btnContinuar.style.display = 'none';
    }

    const btnPagarFinal = document.getElementById('btnPagarFinal');
    if (btnPagarFinal) {
        btnPagarFinal.style.display = 'block';
    }

    setTimeout(() => {
        const carrito = document.getElementById('carrito');
        if (carrito) {
            carrito.scrollTo({ top: carrito.scrollHeight, behavior: 'smooth' });
        }
    }, 100);
}
  

function ocultarFormulario() {
    const datosCliente = document.getElementById('datosCliente');
    if (datosCliente) {
        datosCliente.style.display = 'none';
    }
    
    const btnContinuar = document.getElementById('btnContinuar');
    if (btnContinuar) {
        btnContinuar.style.display = 'block';
    }
    
    const btnPagarFinal = document.getElementById('btnPagarFinal');
    if (btnPagarFinal) {
        btnPagarFinal.style.display = 'none';
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
    console.log(`👁️ Observando ${lazyImages.length} imágenes en cards`);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.card-giratoria').forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.transition = 'transform 0.5s ease, box-shadow 0.3s ease';
      card.style.boxShadow = '0 15px 35px rgba(0,0,0,0.2)';
    });
    card.addEventListener('mouseleave', () => {
      card.style.boxShadow = '';
    });
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

  document.addEventListener('click', (e) => {
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

  window.addEventListener("load", ajustarPosicionesPaneles);
  window.addEventListener("resize", ajustarPosicionesPaneles);

  const btnProductos = document.getElementById("btnProductos");
  if (btnProductos) {
    btnProductos.addEventListener("click", () => {
      const panelGrupos = document.getElementById("panelGrupos");
      if (panelGrupos) panelGrupos.classList.remove("oculta");
      setTimeout(ajustarPosicionesPaneles, 0);
    });
  }

  document.addEventListener('change', (e) => {
    if (e.target.id && e.target.id.startsWith('talle_')) {
      const idProducto = e.target.id.replace('talle_', '');
      const talleSeleccionado = e.target.value;
      if (talleSeleccionado) actualizarStockPorTalle(idProducto, talleSeleccionado);
    }
  });

  const btnSubcategorias = document.getElementById("btnSubcategorias");
  if (btnSubcategorias) {
    btnSubcategorias.addEventListener("click", () => {
      const panelSub = document.getElementById("panelSubcategorias");
      if (panelSub) panelSub.classList.remove("oculta");
      setTimeout(ajustarPosicionesPaneles, 0);
    });
  }

function cargarMercadoPagoJS() {
  return new Promise((resolve, reject) => {
    if (window.mercadoPagoCargado) return resolve();

    const cargar = () => {
      const script = document.createElement('script');
      script.src = 'static/js/mercadopago.js';
      script.async = true; // No bloquea el renderizado
      script.onload = async () => {
        window.mercadoPagoCargado = true;
        resolve();
      };
      script.onerror = reject;
      document.head.appendChild(script);
    };

    // Diferir la carga a un momento de inactividad
    if ('requestIdleCallback' in window) {
      requestIdleCallback(cargar, { timeout: 2000 });
    } else {
      setTimeout(cargar, 1000); // fallback para navegadores antiguos
    }
  });
}

let pagando = false;

document.getElementById('btnPagarFinal')?.addEventListener('click', async () => {
  if (pagando) return;
  pagando = true;
  try {
    await cargarMercadoPagoJS();
    await window.pagarTodoJunto();
  } finally {
    pagando = false;
  }
});

  document.addEventListener("click", (e) => {
    const carritoDiv = document.getElementById("carrito");
    const toggleBtn = document.getElementById("toggleCarrito");
    if (carritoDiv && toggleBtn) {
      const visible = carritoDiv.style.display === "block";
      const clicFueraCarrito = !carritoDiv.contains(e.target) && !toggleBtn.contains(e.target);
      if (visible && clicFueraCarrito) carritoDiv.style.display = "none";
    }

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
  });

  const ordenSelect = document.getElementById("ordenPrecio");
  if (ordenSelect) {
    ordenSelect.addEventListener("change", (e) => {
      if (!window.currentGrupo) {
        console.warn("No hay grupo seleccionado. No se puede ordenar.");
        return;
      }
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
      const cont = document.getElementById("productos");
      if (!cont) return;
      cont.innerHTML = "";
      productosFiltrados.forEach(p => cont.appendChild(renderProducto(p)));
      setTimeout(() => document.querySelectorAll('.fade-reorder').forEach(el => el.classList.remove('fade-reorder')), 50);
      paginaActual = 1;
      productosFiltradosActuales = productosFiltrados;
      renderPaginacion(productosFiltrados);
    });
  }

  document.getElementById('volverArriba').onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });

document.getElementById('loginToggleBtn').onclick = () => {
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

  document.querySelector('.logo').addEventListener('click', function() {
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
});
