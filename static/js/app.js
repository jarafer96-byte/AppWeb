const configWhatsApp = "{{ config.whatsapp }}";
const email = window.email;
const URL_BACKEND = "https://mpagina.onrender.com"; 
const usarFirestore = false;  

if (window.email) {
    email = window.email;
}

let scrollTimer;
let isScrolling = false;

document.addEventListener('DOMContentLoaded', () => {
  
  let isScrolling = false;
  let scrollTimer;
  
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

    let touchStartTime = 0;
    let touchStartX = 0;
    let touchStartY = 0;
    
    card.addEventListener('touchstart', (e) => {
      touchStartTime = Date.now();
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
    }, { passive: true });
    
    card.addEventListener('touchend', (e) => {
      const touchEndTime = Date.now();
      const touchDuration = touchEndTime - touchStartTime;
      const touchEndX = e.changedTouches[0].clientX;
      const touchEndY = e.changedTouches[0].clientY;
      const deltaX = Math.abs(touchEndX - touchStartX);
      const deltaY = Math.abs(touchEndY - touchStartY);
      
      if (touchDuration < 300 && deltaX < 10 && deltaY < 10) {
        const girarBtn = card.querySelector('.btn-girar');
        if (girarBtn) {
          girarBtn.click();
        }
      }
    });
  });
  
  const toggleCarrito = document.getElementById('toggleCarrito');
    let mpCargando = false;
    
    // Función para cargar MP
    function cargarMP() {
      if (window.mpCargado || mpCargando) return;
      
      mpCargando = true;
      const script = document.createElement('script');
      script.src = 'https://sdk.mercadopago.com/js/v2';
      script.defer = true;
      script.onload = () => {
        window.mpCargado = true;
        mpCargando = false;
        console.log('💰 MercadoPago listo para pagos');
      };
      document.head.appendChild(script);
    }
    
    // 1. Cargar al hacer clic en el carrito
    if (toggleCarrito) {
      toggleCarrito.addEventListener('click', cargarMP);
    }
    
    // 2. Cargar cuando el usuario está cerca (IntersectionObserver)
    if (toggleCarrito && 'IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          cargarMP();
          observer.disconnect();
        }
      }, { rootMargin: '300px' });
      observer.observe(toggleCarrito);
    }
    
    // 3. Cargar inmediatamente si es admin
    if (window.modoAdmin) {
      cargarMP();
    }
 
  function loadVisibleImagesFirst() {
    const lazyImages = document.querySelectorAll('.card-giratoria img[data-src]');
    if (lazyImages.length === 0) return;
    
    const viewportHeight = window.innerHeight;
    let loadedCount = 0;
    
    lazyImages.forEach(img => {
      const rect = img.getBoundingClientRect();
      const isVisible = rect.top < viewportHeight + 300 && rect.bottom > -100;
      
      if (isVisible && img.dataset.src) {
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
    
    if (loadedCount > 0) {
      console.log(`🖼️ Lazy: Cargadas ${loadedCount} imágenes en cards`);
    }
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
      }, {
        rootMargin: window.innerWidth < 768 ? '200px' : '100px',
        threshold: 0.01
      });

      lazyImages.forEach(img => observer.observe(img));
      
      console.log(`👁️ Observando ${lazyImages.length} imágenes en cards`);
    }
  }
  
  // 3. Inicializar lazy loading
  setTimeout(loadVisibleImagesFirst, 300);
  setTimeout(setupEnhancedLazyLoading, 800);
  
  // 4. Listener unificado de scroll
  window.addEventListener('scroll', () => {
    // Throttling para lazy loading
    if (!isScrolling) {
      isScrolling = true;
      loadVisibleImagesFirst();
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        loadVisibleImagesFirst();
        isScrolling = false;
      }, 150);
    }
    
    // Botón volver arriba
    const btnArriba = document.getElementById('volverArriba');
    if (btnArriba) {
      btnArriba.style.display = window.scrollY > 300 ? 'block' : 'none';
      btnArriba.style.backgroundColor = 'white';
      btnArriba.style.color = 'black';
    }
    
    // Botón login toggle
    const btnLogin = document.getElementById('loginToggleBtn');
    if (btnLogin && !window.modoAdmin) {
      const isBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 100;
      btnLogin.style.display = isBottom ? 'block' : 'none';
    }
  }, { passive: true });
  
  // 5. Click en botones girar/reversa
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('btn-girar') || 
        e.target.classList.contains('btn-reversa')) {
      const card = e.target.closest('.card-giratoria');
      if (card) {
        setTimeout(() => {
          const images = card.querySelectorAll('img[data-src]');
          images.forEach(img => {
            if (img.dataset.src) {
              img.src = img.dataset.src;
              img.removeAttribute('data-src');
            }
          });
        }, 100);
      }
    }
  });
  
  console.log("✅ Interactividad de cards + lazy loading inicializada");

  // 6. Gestión de paneles
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
  
  // 8. URL params y modo admin
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get("token");

  if (token) {
    window.modoAdmin = true;
    window.tokenAdmin = token;
    document.getElementById("logoutAdminWrapper").style.display = "block";
  } else {
    window.modoAdmin = false;
  }

  window.stockPorTalleData = {};
  
  // 9. Cambio de talles
  document.addEventListener('change', (e) => {
    if (e.target.id && e.target.id.startsWith('talle_')) {
      const idProducto = e.target.id.replace('talle_', '');
      const talleSeleccionado = e.target.value;
      if (talleSeleccionado) {
        actualizarStockPorTalle(idProducto, talleSeleccionado);
      }
    }
  });
  
  // 10. Botón subcategorías
  const btnSubcategorias = document.getElementById("btnSubcategorias");
  if (btnSubcategorias) {
    btnSubcategorias.addEventListener("click", () => {
      const panelSub = document.getElementById("panelSubcategorias");
      if (panelSub) panelSub.classList.remove("oculta");
      setTimeout(ajustarPosicionesPaneles, 0);
    });
  }

  // 11. Listener unificado de clicks en documento
  document.addEventListener("click", (e) => {
    // Botones grupo/subgrupo
    if (e.target.classList.contains("btn-grupo")) {
      console.log("🟢 Click en botón grupo:", e.target.textContent);
      setTimeout(ajustarPosicionesPaneles, 0);
      return;
    }
    
    if (e.target.classList.contains("btn-subgrupo")) {
      console.log("🟢 Click en botón subgrupo:", e.target.textContent);
      return;
    }

    // Cerrar carrito al hacer click fuera
    const carritoDiv = document.getElementById("carrito");
    const toggleBtn = document.getElementById("toggleCarrito");
    if (carritoDiv && toggleBtn) {
      const visible = carritoDiv.style.display === "block";
      const clicFueraCarrito = !carritoDiv.contains(e.target) && !toggleBtn.contains(e.target);
      if (visible && clicFueraCarrito) {
        carritoDiv.style.display = "none";
      }
    }

    // Cerrar paneles al hacer click fuera
    const panelGrupos = document.getElementById("panelGrupos");
    const panelSub = document.getElementById("panelSubcategorias");
    if (panelGrupos && panelSub) {
      const esClickDentroGrupos = panelGrupos.contains(e.target);
      const esClickDentroSub = panelSub.contains(e.target);
      const esBotonGrupo = e.target.classList.contains("btn-grupo");
      const esBotonSubgrupo = e.target.classList.contains("btn-subgrupo");
      const esBotonNavegacion = !!e.target.closest(".barra-navegacion");

      if (!esClickDentroGrupos && !esClickDentroSub && 
          !esBotonGrupo && !esBotonSubgrupo && !esBotonNavegacion) {
        panelGrupos.classList.add("oculta");
        panelSub.classList.add("oculta");
      }
    }
  });

  // 12. Ordenar por precio
  const ordenSelect = document.getElementById("ordenPrecio");
  if (ordenSelect) {
    ordenSelect.addEventListener("change", (e) => {
      const valor = e.target.value; 

      const grupoActivoBtn = document.querySelector(".btn-grupo.active");
      const grupoActivo = grupoActivoBtn ? grupoActivoBtn.textContent.trim() : null;

      const subActivoBtn = document.querySelector(".btn-subgrupo.active");
      const subActivo = subActivoBtn ? subActivoBtn.textContent.trim() : null;

      let productosFiltrados = window.todosLosProductos;

      if (grupoActivo) {
        productosFiltrados = productosFiltrados.filter(
          p => p.grupo?.toLowerCase() === grupoActivo.toLowerCase()
        );
      }
      if (subActivo) {
        productosFiltrados = productosFiltrados.filter(
          p => p.subgrupo?.toLowerCase() === subActivo.toLowerCase()
        );
      }

      productosFiltrados.sort((a, b) => {
        const pa = parseFloat(a.precio) || 0;
        const pb = parseFloat(b.precio) || 0;
        return valor === "asc" ? pa - pb : pb - pa;
      });

      const cont = document.getElementById("productos");
      if (!cont) return;

      cont.innerHTML = "";
      productosFiltrados.forEach((p) => {
        const card = renderProducto(p);
        cont.appendChild(card);
        setTimeout(() => card.classList.remove("fade-reorder"), 50);
      });
    });
  }

  // 13. Modo admin
  if (window.modoAdmin) {
    const adminCard = document.getElementById("adminCard");
    if (adminCard) adminCard.classList.remove("d-none");

    const btnConfigMP = document.getElementById("configurarMP");
    if (btnConfigMP) {
      btnConfigMP.classList.remove("d-none");
    }
  }

  // 14. MercadoPago
  async function initMercadoPago() {
    try {
      const resp = await fetch(`${URL_BACKEND}/api/mp_public_key?email=${encodeURIComponent(email)}`);
      const data = await resp.json();

      if (data.public_key) {
        window.mp = new MercadoPago(data.public_key, { locale: 'es-AR' });
        const pagarBtn = document.getElementById('btn_pagar');
        if (pagarBtn) pagarBtn.disabled = false;
      } else {
        const pagarBtn = document.getElementById('btn_pagar');
        if (pagarBtn) pagarBtn.disabled = true;
      }
    } catch (err) {
      const pagarBtn = document.getElementById('btn_pagar');
      if (pagarBtn) pagarBtn.disabled = true;
    }
  }

  initMercadoPago();
  
  async function pagarConMercadoPago() {
    try {
      if (!carrito.length) {
        return;
      }

      const response = await fetch("https://mpagina.onrender.com/pagar", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          carrito,
          email_vendedor: email,
          url_retorno: window.location.href
        })
      });

      let data = null;
      const contentType = response.headers.get("content-type") || "";

      if (response.ok && contentType.includes("application/json")) {
        try {
          data = await response.json();
        } catch {
          return;
        }
      } else {
        return;
      }

      if (data && data.preference_id && window.mp) {
        window.orden_id = data.external_reference;

        window.mp.checkout({
          preference: { id: data.preference_id },
          autoOpen: true
        });
      } else if (data && data.init_point) {
        window.orden_id = data.external_reference;
        window.location.href = data.init_point;
      }
    } catch {
      return;
    }
  }

  const pagarBtn = document.getElementById('btn_pagar');
  if (pagarBtn) {
    pagarBtn.addEventListener("click", pagarConMercadoPago);
  }

  // 15. Verificación de configuración MP
  setTimeout(() => {
    const urlParams = new URLSearchParams(window.location.search);
    
    if (urlParams.get('mp_configurado') === 'true') {
        const emailVendedor = urlParams.get('email');
        console.log('✅ Mercado Pago configurado exitosamente para:', emailVendedor);
        
        alert('✅ ¡Mercado Pago configurado exitosamente! Ahora puedes recibir pagos.');

        const nuevaURL = window.location.pathname + '?email=' + encodeURIComponent(emailVendedor);
        window.history.replaceState({}, document.title, nuevaURL);
        
        setTimeout(() => {
            location.reload();
        }, 1500);
    }
    
    if (urlParams.get('mp_error') === '1') {
        alert('❌ Hubo un error al configurar Mercado Pago. Por favor, intenta nuevamente.');
        
        const nuevaURL = window.location.pathname;
        window.history.replaceState({}, document.title, nuevaURL);
    }
  }, 100);
});    

document.getElementById('volverArriba').onclick = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};
    
document.getElementById('loginToggleBtn').onclick = () => {
  const form = document.getElementById('loginFloatingForm');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
};
    
document.getElementById("tallesProd").addEventListener("input", function() {
  const talles = this.value.split(",").map(t => t.trim()).filter(Boolean);
  const container = document.getElementById("stockPorTalleContainer");
  const simpleContainer = document.getElementById("stockSimple");
  
  console.log("⌨️ Talles ingresados:", talles);
  
  if (talles.length > 0) {
    container.style.display = "block";
    simpleContainer.style.display = "none";
    
    const stockPorTalleInput = document.getElementById("stockPorTalle");
    if (stockPorTalleInput) {
      const estaEditando = !!window.productoEditandoId;
      const stockEstaVacio = !stockPorTalleInput.value.trim();
      
      console.log("📝 Estado:", {
        editando: estaEditando,
        stockVacio: stockEstaVacio,
        valorActual: stockPorTalleInput.value
      });
      if ((!estaEditando && stockEstaVacio) || stockEstaVacio) {
        const nuevoStock = talles.map(t => `${t}:0`).join(", ");
        stockPorTalleInput.value = nuevoStock;
        console.log("🔄 Stock por talle inicializado:", nuevoStock);
      } 

      else if (estaEditando && !stockEstaVacio) {
        console.log("📌 Manteniendo stock existente durante edición");
      }

      else if (!estaEditando && !stockEstaVacio) {
        try {
          const stockExistente = {};
          stockPorTalleInput.value.split(",").forEach(item => {
            const parts = item.split(":").map(s => s.trim());
            if (parts.length >= 2) {
              const talle = parts[0];
              const stock = parseInt(parts[1]) || 0;
              stockExistente[talle] = stock;
            }
          });

          const nuevoStock = talles.map(talle => {
            if (stockExistente[talle] !== undefined) {
              return `${talle}:${stockExistente[talle]}`;
            } else {
              return `${talle}:0`; 
            }
          }).join(", ");

          stockPorTalleInput.value = nuevoStock;
          console.log("🔄 Stock por talle actualizado manteniendo valores:", nuevoStock);
          
        } catch (error) {
          console.error("❌ Error procesando stock:", error);
          const nuevoStock = talles.map(t => `${t}:0`).join(", ");
          stockPorTalleInput.value = nuevoStock;
        }
      }
    }
    
  } else {
    container.style.display = "none";
    simpleContainer.style.display = "block";
    console.log("📭 Sin talles, mostrando stock simple");
  }
});
function renderizarProductos(productos) {
  console.log("🎨 Renderizando productos:", productos.length);
  
  const cont = document.getElementById("productos");
  if (!cont) {
    console.warn("⚠️ No se encontró el contenedor #productos");
    return;
  }
  
  cont.innerHTML = ""; 
  
  productos.forEach(p => {
    const card = renderProducto(p);
    cont.appendChild(card);

    setTimeout(() => {
      card.classList.remove("fade-reorder");
      card.classList.add("show");
    }, 50);
  });
  
  console.log("✅ " + productos.length + " productos renderizados");
}
function cargarProductoCompletoParaEditar(id_base) {
  const producto = window.todosLosProductos?.find(p => p.id_base === id_base);
  if (producto) {
    cargarProductoEnFormulario(producto);
  } else {
    alert("❌ No se encontró el producto para editar");
  }
}
function cargarProductoEnFormulario(producto) {
  console.log("📝 Cargando producto para editar:", producto.nombre);
  console.log("🔍 Datos del producto recibidos:", {
    talles: producto.talles,
    stock_por_talle: producto.stock_por_talle,
    tiene_talles_array: Array.isArray(producto.talles),
    tiene_stock_por_talle: !!producto.stock_por_talle,
    fotos_adicionales_count: producto.fotos_adicionales ? producto.fotos_adicionales.length : 0
  });
  
  const adminCard = document.getElementById("adminCard");
  adminCard.classList.remove("d-none");
  
  toggleModoEdicion(true);
  
  document.getElementById("nombreProd").value = producto.nombre || "";
  document.getElementById("precioProd").value = producto.precio || "";
  document.getElementById("descripcionProd").value = producto.descripcion || "";
  document.getElementById("grupoProd").value = producto.grupo || "";
  document.getElementById("subgrupoProd").value = producto.subgrupo || "";
  
  let tallesArray = [];
  console.log("🔍 Analizando talles del producto...");
  
  if (Array.isArray(producto.talles)) {
    tallesArray = producto.talles;
    console.log("✅ Talles como array:", tallesArray);
    document.getElementById("tallesProd").value = producto.talles.join(", ");
  } else if (typeof producto.talles === 'string') {
    tallesArray = producto.talles.split(",").map(t => t.trim()).filter(Boolean);
    console.log("✅ Talles como string convertido:", tallesArray);
    document.getElementById("tallesProd").value = producto.talles;
  } else {
    console.log("⚠️ No se encontraron talles o formato inválido:", producto.talles);
    document.getElementById("tallesProd").value = "";
  }
  
  console.log("📋 Talles finales:", tallesArray);
  
  if (tallesArray.length > 0) {
    console.log("🔄 Producto CON talles, mostrando stock por talle");
    document.getElementById("stockPorTalleContainer").style.display = "block";
    document.getElementById("stockSimple").style.display = "none";
    
    let stockPorTalleStr = "";
    
    if (producto.stock_por_talle && Object.keys(producto.stock_por_talle).length > 0) {
      const stockPorTalle = producto.stock_por_talle;
      console.log("📊 Stock por talle original:", stockPorTalle);
      
      const stockFiltrado = {};
      let tallesFiltrados = 0;
      let tallesIgnorados = [];
      
      tallesArray.forEach(talle => {
        if (stockPorTalle[talle] !== undefined) {
          stockFiltrado[talle] = stockPorTalle[talle];
          tallesFiltrados++;
          console.log(`✅ Talle "${talle}" encontrado en stock: ${stockPorTalle[talle]}`);
        } else {
          stockFiltrado[talle] = 0; // Talle nuevo, stock en 0
          console.log(`⚠️ Talle "${talle}" NO encontrado en stock, asignando 0`);
        }
      });
      
      Object.keys(stockPorTalle).forEach(talle => {
        if (!tallesArray.includes(talle) && talle !== "unico") {
          tallesIgnorados.push(`${talle}:${stockPorTalle[talle]}`);
          console.log(`🗑️ Talle "${talle}" será ignorado porque no está en tallesArray`);
        }
      });
      
      if (tallesIgnorados.length > 0) {
        console.log("📌 Talles ignorados del stock:", tallesIgnorados.join(", "));
      }

      stockPorTalleStr = Object.entries(stockFiltrado)
        .map(([talle, stock]) => `${talle}:${stock}`)
        .join(", ");
      
      console.log("🔄 Stock por talle filtrado:", stockFiltrado);
      console.log("📝 String generado:", stockPorTalleStr);
      
    } else {
      stockPorTalleStr = tallesArray.map(t => `${t}:0`).join(", ");
      console.log("➕ Creando stock inicial:", stockPorTalleStr);
    }
    
    document.getElementById("stockPorTalle").value = stockPorTalleStr;
    
  } else {
    console.log("🔄 Producto SIN talles, mostrando stock simple");
    document.getElementById("stockPorTalleContainer").style.display = "none";
    document.getElementById("stockSimple").style.display = "block";
    
    let stockGeneral = 0;
    if (producto.stock_por_talle && producto.stock_por_talle["unico"] !== undefined) {
      stockGeneral = producto.stock_por_talle["unico"];
      console.log("📊 Stock general (unico):", stockGeneral);
    } else if (producto.stock) {
      stockGeneral = producto.stock;
      console.log("📊 Stock general (stock):", stockGeneral);
    } else {
      console.log("📊 Sin stock definido, usando 0");
    }
    
    document.getElementById("stockGeneral").value = stockGeneral;
  }

  if (producto.imagen_url) {
    const previewFoto = document.getElementById("previewFoto");
    previewFoto.src = producto.imagen_url;
    previewFoto.classList.remove("d-none");
    document.getElementById("btnQuitarFoto").classList.remove("d-none");
    console.log("🖼️ Imagen principal cargada:", producto.imagen_url);
  } else {
    document.getElementById("previewFoto").classList.add("d-none");
    document.getElementById("btnQuitarFoto").classList.add("d-none");
    console.log("🖼️ Sin imagen principal");
  }
  
  const previewDiv = document.getElementById("previewFotosAdicionales");
  if (previewDiv) {
    previewDiv.innerHTML = '';
    
    window.fotosAdicionalesExistentes = producto.fotos_adicionales || [];
    
    if (window.fotosAdicionalesExistentes.length > 0) {
      console.log(`🖼️ Mostrando ${window.fotosAdicionalesExistentes.length} fotos adicionales existentes`);
      
      window.fotosAdicionalesExistentes.forEach((url, index) => {
        const img = document.createElement("img");
        img.src = url;
        img.style.width = '80px';
        img.style.height = '80px';
        img.style.objectFit = 'cover';
        img.style.margin = '5px';
        img.style.borderRadius = '4px';
        img.style.cursor = 'pointer';
        img.style.border = '2px solid #ccc';
        img.title = `Foto adicional ${index + 1}`;
        
        const container = document.createElement("div");
        container.style.position = 'relative';
        container.style.display = 'inline-block';
        
        const btnEliminar = document.createElement("button");
        btnEliminar.innerHTML = "×";
        btnEliminar.style.position = 'absolute';
        btnEliminar.style.top = '-5px';
        btnEliminar.style.right = '-5px';
        btnEliminar.style.background = 'red';
        btnEliminar.style.color = 'white';
        btnEliminar.style.border = 'none';
        btnEliminar.style.borderRadius = '50%';
        btnEliminar.style.width = '20px';
        btnEliminar.style.height = '20px';
        btnEliminar.style.cursor = 'pointer';
        btnEliminar.style.fontSize = '14px';
        btnEliminar.style.fontWeight = 'bold';
        btnEliminar.title = 'Eliminar esta foto';
        
        btnEliminar.onclick = (e) => {
          e.stopPropagation();
          if (confirm(`¿Eliminar foto adicional ${index + 1}?`)) {
            window.fotosAdicionalesExistentes = window.fotosAdicionalesExistentes.filter((_, i) => i !== index);
            cargarProductoEnFormulario(producto);
            console.log(`🗑️ Foto adicional ${index + 1} eliminada`);
          }
        };
        
        img.onclick = () => openModal(url);
        
        container.appendChild(img);
        container.appendChild(btnEliminar);
        previewDiv.appendChild(container);
      });
    } else {
      console.log("🖼️ No hay fotos adicionales existentes");
      previewDiv.innerHTML = '<small class="text-muted">No hay fotos adicionales</small>';
    }
  } else {
    console.log("⚠️ No se encontró el div previewFotosAdicionales");
  }
  
  window.productoEditandoId = producto.id_base;
  console.log("🔑 ID del producto en edición:", window.productoEditandoId);
  
  adminCard.scrollIntoView({ behavior: 'smooth' });
  
  console.log("✅ Producto cargado correctamente en formulario");
  console.log(`📸 Fotos adicionales guardadas para edición: ${window.fotosAdicionalesExistentes ? window.fotosAdicionalesExistentes.length : 0}`);
}
function toggleModoEdicion(editando) {
  const btnCancelar = document.getElementById("btnCancelarEdicion");
  const btnConfirmar = document.getElementById("btnConfirmarProd");
  const titulo = document.getElementById("tituloFormularioAdmin") || document.createElement("h5");
  
  if (editando) {
    if (titulo && titulo.id === "tituloFormularioAdmin") {
      titulo.textContent = "✏️ Editando Producto";
      titulo.classList.add("text-warning");
    }
    
    btnCancelar.style.display = "block";
    btnConfirmar.innerHTML = "💾 Actualizar Producto";
    btnConfirmar.classList.remove("btn-success");
    btnConfirmar.classList.add("btn-warning");
    console.log("🔧 Modo edición activado");
  } else {
    if (titulo && titulo.id === "tituloFormularioAdmin") {
      titulo.textContent = "➕ Nuevo Producto";
      titulo.classList.remove("text-warning");
    }
    
    btnCancelar.style.display = "none";
    btnConfirmar.innerHTML = "✅ Confirmar";
    btnConfirmar.classList.remove("btn-warning");
    btnConfirmar.classList.add("btn-success");
    console.log("🔧 Modo creación activado");
  }
}
function resetearFormularioAdmin() {
  console.log("🔄 Reseteando formulario admin...");

  document.getElementById("nombreProd").value = "";
  document.getElementById("precioProd").value = "";
  document.getElementById("descripcionProd").value = "";
  document.getElementById("tallesProd").value = "";
  document.getElementById("stockGeneral").value = "0";
  document.getElementById("stockPorTalle").value = "";
  document.getElementById("grupoProd").value = "";
  document.getElementById("subgrupoProd").value = "";
  
  document.getElementById("stockPorTalleContainer").style.display = "none";
  document.getElementById("stockSimple").style.display = "block";
  
  document.getElementById("previewFoto").src = "";
  document.getElementById("previewFoto").classList.add("d-none");
  document.getElementById("btnQuitarFoto").classList.add("d-none");
  document.getElementById("inputFoto").value = "";
  window.fotoOptimizada = null;
  
  const previewDiv = document.getElementById("previewFotosAdicionales");
  if (previewDiv) {
    previewDiv.innerHTML = '';
    console.log("✅ Preview de fotos adicionales limpiado");
  }
  
  const fotosInput = document.getElementById("fotosAdicionales");
  if (fotosInput) {
    fotosInput.value = "";
    console.log("✅ Input de fotos adicionales limpiado");
  }
 
  window.fotosAdicionalesExistentes = null;
  console.log("✅ Variables de fotos adicionales limpiadas");

  const btnConfirmar = document.getElementById("btnConfirmarProd");
  if (btnConfirmar) {
    btnConfirmar.innerHTML = "✅ Confirmar";
    btnConfirmar.classList.remove("btn-warning");
    btnConfirmar.classList.add("btn-success");
    console.log("✅ Botón cambiado a modo creación");
  }

  const btnCancelar = document.getElementById("btnCancelarEdicion");
  if (btnCancelar) {
    btnCancelar.style.display = "none";
    console.log("✅ Botón cancelar ocultado");
  }
  
  window.productoEditandoId = null;
  console.log("✅ ID de edición limpiado");
  
  if (typeof toggleModoEdicion === "function") {
    toggleModoEdicion(false);
  }
  
  console.log("✅ Formulario admin completamente reseteado");
}
function actualizarStockPorTalle(idProducto, talleSeleccionado) {
  console.log(`📊 [actualizarStockPorTalle] id: ${idProducto}, talle: ${talleSeleccionado}`);
  
  const stockSpan = document.getElementById(`stock_${idProducto}`);
  const cantidadInput = document.getElementById(`cantidad_${idProducto}`);
  const agregarBtn = document.getElementById(`btn_agregar_${idProducto}`);
  
  if (!stockSpan || !cantidadInput || !agregarBtn) {
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

  stockSpan.textContent = stockDisponible > 0 ? stockDisponible : "Sin stock";
  
  if (stockDisponible > 0) {
    stockSpan.classList.remove("text-danger");
    stockSpan.classList.add("text-success");
    setTimeout(() => stockSpan.classList.remove("text-success"), 1000);
    
    cantidadInput.max = stockDisponible;
    cantidadInput.disabled = false;
    const valorActual = parseInt(cantidadInput.value) || 1;
    cantidadInput.value = Math.min(valorActual, stockDisponible);
    
    agregarBtn.disabled = false;
    agregarBtn.style.opacity = "1";
    agregarBtn.textContent = "Agregar al carrito";
  } else {
    stockSpan.classList.remove("text-success");
    stockSpan.classList.add("text-danger");
    
    cantidadInput.disabled = true;
    cantidadInput.value = "0";
    
    agregarBtn.disabled = true;
    agregarBtn.style.opacity = "0.5";
    agregarBtn.textContent = "Sin stock";
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

const itemsPorPagina = 12;
let totalPaginas = 0;

const modoAdmin = window.tokenAdminEmail ? true : false;

if (modoAdmin) {
  document.getElementById("adminCard").classList.remove("d-none");
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
    
function girarCard(elemento) {
  const cardContenedor = elemento.closest('.card-contenedor');
  if (cardContenedor) {
    const estaGirada = cardContenedor.style.transform === 'rotateY(180deg)';
    cardContenedor.style.transform = estaGirada ? 'rotateY(0deg)' : 'rotateY(180deg)';
  }
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


async function pagarTodoJunto() {
    console.log("🛒 Iniciando proceso de pago...");
    
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

    const orden_id = 'ORD_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    function convertirPrecio(precio) {
        if (typeof precio === 'number') {
            return precio;
        }
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
    
    const payload = {
        email_vendedor: email,
        carrito: itemsCarrito,  
        items_mp: itemsMP,      
        total: totalCalculado,
        cliente_nombre: `${nombre} ${apellido}`.trim(),
        cliente_email: emailCliente,
        cliente_telefono: telefono,
        orden_id: orden_id,
        url_retorno: window.location.href
    };
    
    console.log("📦 Payload para el pago:", payload);
    console.log("💰 Total calculado:", totalCalculado);
    console.log("🛒 Items procesados:", itemsCarrito.length);
    
    itemsCarrito.forEach((item, idx) => {
        console.log(`  ${idx+1}. ${item.nombre}: $${item.precio} x ${item.cantidad} = $${item.subtotal}`);
    });
    
    try {
        const btnPagarFinal = document.getElementById('btnPagarFinal');
        if (btnPagarFinal) {
            btnPagarFinal.disabled = true;
            btnPagarFinal.textContent = 'Procesando...';
        }
        
        const response = await fetch(`${URL_BACKEND}/pagar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log("✅ Respuesta del backend:", data);
        
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
            
            console.log("➡️ Redirigiendo a Mercado Pago...");
            window.location.href = data.init_point;
        } else if (data.preference_id && window.mp) {
            localStorage.setItem('ultima_orden_id', orden_id);
            
            window.mp.checkout({
                preference: { id: data.preference_id },
                autoOpen: true
            });
        } else {
            console.warn("Respuesta inesperada del backend:", data);
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

function vaciarCarrito() {
    carrito = [];
    actualizarCarrito();
    ocultarFormulario(); 
}

function toggleModoAdmin(activo) {
  document.querySelectorAll(".btnEliminarCard").forEach(btn => {
    if (activo) {
      btn.classList.remove("d-none");
    } else {
      btn.classList.add("d-none");
    }
  });
}
    
function abrirConfigMercadoPago() {
    console.log("⚙️ Redirigiendo a configuración de Mercado Pago...");
    const urlRetorno = window.location.href;

    const configUrl = `${URL_BACKEND}/conectar_mp?email=${encodeURIComponent(email)}&url_retorno=${encodeURIComponent(urlRetorno)}`;
    
    console.log("🔗 Redirigiendo a:", configUrl);
    console.log("📍 URL de retorno (página del vendedor):", urlRetorno);
    
    window.location.href = configUrl;
}
    
async function eliminarProducto(id_base) {
  console.log("[ELIMINAR_PRODUCTO] 🔔 Click en botón eliminar → id_base:", id_base);

  try {
    console.log("[ELIMINAR_PRODUCTO] 📡 Enviando request al backend...");
    const resp = await fetch("https://mpagina.onrender.com/eliminar-producto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_base, email }) 
    });

    console.log("[ELIMINAR_PRODUCTO] 📥 Status HTTP:", resp.status);
    const data = await resp.json();
    console.log("[ELIMINAR_PRODUCTO] 📄 Respuesta JSON:", data);

    if (data.status === "ok") {
      const card = document.querySelector(`[data-id="${id_base}"]`);
      if (card) {
        card.remove();
        console.log("[ELIMINAR_PRODUCTO] 🗑️ Card eliminada del DOM:", id_base);
      } else {
        console.warn("[ELIMINAR_PRODUCTO] ⚠️ No se encontró la card en el DOM para id_base:", id_base);
      }
    } else {
      console.error("[ELIMINAR_PRODUCTO] ❌ Error reportado por backend:", data.error);
      alert("Error al eliminar producto: " + data.error);
    }
  } catch (err) {
    console.error("[ELIMINAR_PRODUCTO] 💥 Excepción inesperada:", err);
    alert("Error al eliminar producto: " + err.message);
  }
}

async function optimizarImagen(file) {
  console.log(`📂 [optimizarImagen] Iniciando optimización: ${file.name} (${file.size} bytes)`);

  const imgUrl = URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        console.log(`✅ [optimizarImagen] Imagen cargada: ${image.width}x${image.height}px`);
        resolve(image);
      };
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

    console.log(`📐 [optimizarImagen] Escalado → newW=${newW}, newH=${newH}, offsetX=${offsetX}, offsetY=${offsetY}`);
    ctx.drawImage(img, offsetX, offsetY, newW, newH);

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(b => {
        if (b && b.size > 0) {
          console.log(`✅ [optimizarImagen] Blob generado (${b.size} bytes)`);
          resolve(b);
        } else {
          reject(new Error("❌ No se pudo generar WebP"));
        }
      }, "image/webp", 0.8);
    });

    return blob;
  } finally {
    URL.revokeObjectURL(imgUrl);
    console.log(`🧹 [optimizarImagen] URL revocada`);
  }
}

document.getElementById("inputFoto").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const blobOptimizado = await optimizarImagen(file);
    window.fotoOptimizada = blobOptimizado;

    const urlPreview = URL.createObjectURL(blobOptimizado);
    const imgPreview = document.getElementById("previewFoto");
    imgPreview.src = urlPreview;
    imgPreview.classList.remove("d-none");

    console.log("👁️ Preview inmediato mostrado");
  } catch (err) {
    console.error("💥 Error al optimizar imagen:", err);
    alert("❌ No se pudo optimizar la imagen");
  }
});

document.getElementById("btnConfirmarProd").addEventListener("click", async () => {
  const email = "{{ session.get('email') or '' }}";
  if (!email) {
    alert("❌ No hay email de admin, no se puede guardar");
    return;
  }

  try {
    let precioViejo = 0;
    let precioAnteriorParaEnviar = 0; 
    
    if (window.productoEditandoId) {
      const productoExistente = window.todosLosProductos?.find(p => p.id_base === window.productoEditandoId);
      if (productoExistente) {
        precioViejo = parseFloat(productoExistente.precio) || 0;
        console.log(`💰 Precio anterior encontrado: $${precioViejo}`);
        const precioNuevo = parseFloat(document.getElementById("precioProd").value);
        
        if (!isNaN(precioNuevo) && precioViejo > precioNuevo) {
          precioAnteriorParaEnviar = precioViejo;
          console.log(`🔥 OFERTA DETECTADA: $${precioViejo} → $${precioNuevo} (Ahorro: $${(precioViejo - precioNuevo).toFixed(2)})`);
        } else if (precioViejo < precioNuevo) {
          precioAnteriorParaEnviar = 0;
          console.log(`📈 Precio aumentó: $${precioViejo} → $${precioNuevo} (NO es oferta)`);
        } else {
          precioAnteriorParaEnviar = 0;
          console.log(`📊 Precio sin cambios: $${precioViejo}`);
        }
      }
    }

    let foto_url = "";
    if (window.fotoOptimizada) {
      const formData = new FormData();
      formData.append("file", window.fotoOptimizada, "producto.jpg");
      formData.append("email", email);

      console.log("📡 Subiendo foto principal...");
      const respFoto = await fetch("https://mpagina.onrender.com/subir-foto", {
        method: "POST",
        body: formData
      });

      if (!respFoto.ok) {
        const text = await respFoto.text();
        throw new Error(`Error al subir foto: ${respFoto.status} ${text}`);
      }

      const fotoData = await respFoto.json();
      foto_url = fotoData.url || "";
      console.log("✅ Foto principal subida:", foto_url);
    } else if (window.productoEditandoId) {
      const productoExistente = window.todosLosProductos?.find(p => p.id_base === window.productoEditandoId);
      foto_url = productoExistente?.imagen_url || "";
      console.log("🔄 Manteniendo foto principal existente:", foto_url);
    }
    const fotosAdicionalesUrls = [];
    
    if (window.fotosAdicionalesExistentes && window.fotosAdicionalesExistentes.length > 0) {
      fotosAdicionalesUrls.push(...window.fotosAdicionalesExistentes);
      console.log(`🔄 Manteniendo ${window.fotosAdicionalesExistentes.length} fotos adicionales existentes`);
    }
    
    const fotosInput = document.getElementById('fotosAdicionales');
    if (fotosInput && fotosInput.files && fotosInput.files.length > 0) {
      console.log(`📸 Subiendo ${fotosInput.files.length} nuevas fotos adicionales...`);
      
      for (let i = 0; i < fotosInput.files.length; i++) {
        try {
          const file = fotosInput.files[i];

          let blobOptimizado;
          try {
            blobOptimizado = await optimizarImagen(file);
          } catch (e) {
            console.warn(`⚠️ No se pudo optimizar foto ${i+1}, subiendo original:`, e);
            blobOptimizado = file; 
          }
          
          const formData = new FormData();
          formData.append("file", blobOptimizado, `adicional_${Date.now()}_${i}.jpg`);
          formData.append("email", email);

          const resp = await fetch("https://mpagina.onrender.com/subir-foto", {
            method: "POST",
            body: formData
          });

          if (!resp.ok) {
            const text = await resp.text();
            console.warn(`⚠️ Error subiendo foto adicional ${i+1}: ${resp.status} ${text}`);
            continue; 
          }

          const data = await resp.json();
          if (data.url) {
            fotosAdicionalesUrls.push(data.url);
            console.log(`✅ Foto adicional ${i+1} subida: ${data.url.substring(0, 50)}...`);
          }
        } catch (err) {
          console.error(`❌ Error procesando foto adicional ${i+1}:`, err);
        }
      }
    }

    console.log(`📊 Total fotos adicionales procesadas: ${fotosAdicionalesUrls.length}`);

    const nombre = document.getElementById("nombreProd").value.trim();
    const precioNuevo = parseFloat(document.getElementById("precioProd").value);
    const descripcion = document.getElementById("descripcionProd").value.trim();
    const tallesRaw = document.getElementById("tallesProd").value.trim();
    const grupo = document.getElementById("grupoProd")?.value.trim() || "General";
    const subgrupo = document.getElementById("subgrupoProd")?.value.trim() || "general";

    if (!nombre || isNaN(precioNuevo) || precioNuevo <= 0 || !grupo) {
      alert("❌ Faltan campos obligatorios: nombre/grupo/precio");
      return;
    }
    let stockPorTalle = {};
    const talles = tallesRaw ? tallesRaw.split(",").map(t => t.trim()).filter(Boolean) : [];
    
    if (talles.length > 0) {
      const stockTalleInput = document.getElementById("stockPorTalle").value.trim();
      
      if (stockTalleInput) {
        stockTalleInput.split(",").forEach(item => {
          const parts = item.split(":").map(s => s.trim());
          if (parts.length >= 2) {
            const talle = parts[0];
            const stock = parseInt(parts[1]) || 0;
            if (talle && !isNaN(stock)) {
              stockPorTalle[talle] = stock;
            }
          }
        });
        
        talles.forEach(talle => {
          if (stockPorTalle[talle] === undefined) {
            stockPorTalle[talle] = 0;
          }
        });
      } else {
        talles.forEach(talle => stockPorTalle[talle] = 0);
      }
    } else {
      const stockGeneral = parseInt(document.getElementById("stockGeneral").value) || 0;
      stockPorTalle = {"unico": stockGeneral};
    }

    console.log("📦 Stock procesado:", stockPorTalle);

    if (window.productoEditandoId && precioViejo > precioNuevo) {
      try {
        const historial = JSON.parse(localStorage.getItem('historial_precios') || '{}');
        historial[window.productoEditandoId] = precioViejo;
        localStorage.setItem('historial_precios', JSON.stringify(historial));
        console.log(`💰 Precio anterior guardado en localStorage: $${precioViejo} (backup)`);
      } catch(e) {
        console.log("⚠️ Error guardando en localStorage:", e);
      }
    }

    const producto = {
      nombre: nombre,
      precio: precioNuevo,
      descripcion: descripcion || "",
      talles: talles,
      grupo: grupo,
      subgrupo: subgrupo,
      stock_por_talle: stockPorTalle,
      imagen_url: foto_url,
      fotos_adicionales: fotosAdicionalesUrls,
      precio_anterior: precioAnteriorParaEnviar
    };
    const esEdicion = window.productoEditandoId ? true : false;
    const payload = {
      producto: producto,
      email: email,
      es_edicion: esEdicion
    };

    if (esEdicion) {
      payload.producto.id_base = window.productoEditandoId;
      console.log("🔄 Modo EDICIÓN para ID:", window.productoEditandoId);
      console.log(`💰 precio_anterior a enviar: $${precioAnteriorParaEnviar} ${precioAnteriorParaEnviar > 0 ? '(OFERTA)' : '(sin oferta)'}`);
    } else {
      console.log("➕ Modo CREACIÓN de nuevo producto");
      producto.precio_anterior = 0;
    }

    console.log("📤 Payload para backend:", JSON.stringify(payload, null, 2));
    const endpoint = "https://mpagina.onrender.com/guardar-producto";
    
    const respGuardar = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!respGuardar.ok) {
      const text = await respGuardar.text();
      console.error("❌ Error del servidor:", text);
      throw new Error(`Error al guardar producto: ${respGuardar.status} ${text}`);
    }

    const data = await respGuardar.json();
    console.log("📩 Respuesta backend:", data);

    if (data.status === "ok") {
      const mensaje = esEdicion ? 
        `✅ Producto actualizado correctamente (${fotosAdicionalesUrls.length} fotos adicionales)` : 
        `✅ Producto creado correctamente (${fotosAdicionalesUrls.length} fotos adicionales)`;
      
      const tieneOferta = data.resultado?.tiene_oferta || precioAnteriorParaEnviar > 0;
      const precioAnteriorBackend = data.resultado?.precio_anterior || precioAnteriorParaEnviar;
      
      if (tieneOferta && precioAnteriorBackend > 0) {
        const descuento = Math.round(((precioAnteriorBackend - precioNuevo) / precioAnteriorBackend) * 100);
        alert(`${mensaje}\n🔥 ¡OFERTA DETECTADA! -${descuento}% de descuento`);
        
        console.log(`🎯 OFERTA CONFIRMADA: Antes $${precioAnteriorBackend} → Ahora $${precioNuevo} (-${descuento}%)`);
      } else {
        alert(mensaje);
        console.log(`📊 Producto guardado sin oferta: $${precioNuevo}`);
      }

      resetearFormularioAdmin();
      window.fotosAdicionalesExistentes = null;
      document.getElementById("adminCard").classList.add("d-none");

      setTimeout(() => {
        if (typeof cargarProductos === "function") {
          cargarProductos();
        } else {
          location.reload();
        }
      }, 1000);
      
    } else {
      console.error("❌ Error al guardar producto:", data);
      alert("❌ " + (data.error || data.message || "Error al guardar producto"));
    }
  } catch (err) {
    console.error("💥 Error en flujo de confirmación:", err);
    alert("❌ Error al guardar producto: " + err.message);
  }
});
    
function salirAdmin() {
  console.log("🚪 Saliendo de modo admin, limpiando token...");

  window.modoAdmin = false;
  window.tokenAdmin = null;

  history.replaceState(null, "", "index.html");

  const loginToggleBtn = document.getElementById("loginToggleBtn");
  if (loginToggleBtn) {
    loginToggleBtn.style.display = "none";
    console.log("✅ Botón admin flotante ocultado");
  }
  
  if (window.todosLosProductos) {
    const cont = document.getElementById("productos");
    if (cont) {
      cont.innerHTML = "";
      window.todosLosProductos.forEach(p => cont.appendChild(renderProducto(p)));
      console.log("✅ Productos re-renderizados en modo público, total:", cont.children.length);
    } else {
      console.warn("⚠️ No se encontró el contenedor #productos al salir de admin");
    }
  }

  const logoutWrapper = document.getElementById("logoutAdminWrapper");
  if (logoutWrapper) {
    logoutWrapper.style.display = "none";
    console.log("✅ Botón de logout ocultado");
  } else {
    console.warn("⚠️ No se encontró #logoutAdminWrapper en el DOM");
  }

  const adminCard = document.getElementById("adminCard");
  if (adminCard) {
    adminCard.classList.add("d-none");
    console.log("✅ adminCard ocultado");
  }

  const configurarMP = document.getElementById("configurarMP");
  if (configurarMP) {
    configurarMP.classList.add("d-none");
    console.log("✅ configurarMP ocultado");
  }
}

if (window.modoAdmin) {
  const logoutWrapper = document.getElementById("logoutAdminWrapper");
  if (logoutWrapper) {
    logoutWrapper.style.display = "block";
    console.log("🔑 Modo admin activo, mostrando botón de logout");
  }

  const adminCard = document.getElementById("adminCard");
  if (adminCard) {
    adminCard.classList.remove("d-none");
    console.log("🔑 adminCard mostrado");
  }

  const configurarMP = document.getElementById("configurarMP");
  if (configurarMP) {
    configurarMP.classList.remove("d-none");
    console.log("🔑 configurarMP mostrado");
  }
}

function renderPagina(pagina, productosFiltrados) {
  const cont = document.getElementById("productos");
  totalPaginas = Math.ceil(productosFiltrados.length / itemsPorPagina);
  const inicio = (pagina - 1) * itemsPorPagina;
  const fin = inicio + itemsPorPagina;
  const productosPagina = productosFiltrados.slice(inicio, fin);
  cont.innerHTML = "";
  productosPagina.forEach((p, index) => {
    const esLCP = (pagina === 1 && index === 0);
    cont.appendChild(renderProducto(p, esLCP));
  });
}


function renderPaginacion(productosFiltrados) {
  const pagDiv = document.getElementById("paginacion");
  pagDiv.innerHTML = "";
  totalPaginas = Math.ceil(productosFiltrados.length / itemsPorPagina);

  for (let i = 1; i <= totalPaginas; i++) {
    const btn = document.createElement("button");
    btn.textContent = i;
    btn.className = "btn btn-light mx-1";
    btn.onclick = () => renderPagina(i, productosFiltrados);
    pagDiv.appendChild(btn);
  }
}

let urlProductos = `https://mpagina.onrender.com/api/productos?usuario=${encodeURIComponent(email)}`;
if (window.modoAdmin && window.tokenAdmin) {
  urlProductos += `&token=${encodeURIComponent(window.tokenAdmin)}`;
}

console.log("📡 Solicitando productos desde:", urlProductos);

fetch(urlProductos)
  .then(r => {
    if (!r.ok) {
      throw new Error("HTTP " + r.status);
    }
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
      mostrarGrupo(primerGrupo, null, true);
      if (subgruposPrimer.length > 0) {
        console.log("➡️ Render inicial con subgrupo:", subgruposPrimer[0]);
        filtrarSubcategoria(primerGrupo, subgruposPrimer[0]);
      }
    }

    console.log("✅ Render inicial completado");
  })
  .catch(err => {
    console.error("💥 Error cargando productos:", err);
    const cont = document.getElementById("productos");
    if (cont) cont.innerHTML = "<p>Error al cargar productos.</p>";
  });
    
function mostrarGrupo(nombre, event, auto = false) {
  console.log("🟦 mostrarGrupo llamado con:", { nombre, auto });

  const cont = document.getElementById("productos");
  if (!cont) {
    console.warn("⚠️ No existe #productos en el DOM");
    return;
  }

  document.querySelectorAll('.btn-grupo').forEach(btn => btn.classList.remove('active'));
  if (event?.target) {
    event.target.classList.add('active');
    console.log("👉 Botón de grupo marcado:", event.target.textContent);
  }

  const panel = document.getElementById('panelSubcategorias');
  if (!panel) {
    console.warn("⚠️ No existe #panelSubcategorias en el DOM");
    return;
  }
  panel.innerHTML = "";

  const grupoCanon = String(nombre || "").trim();
  window.currentGrupo = grupoCanon.toLowerCase();
  console.log("🎯 Grupo activo (canon):", grupoCanon);

  const productosGrupo = (window.todosLosProductos || []).filter(
    p => String(p.grupo || "").toLowerCase() === grupoCanon.toLowerCase()
  );
  console.log("📦 Productos encontrados para grupo:", productosGrupo.length);

  const subcategorias = [...new Set(
    productosGrupo.map(p => p.subgrupo).filter(s => s && String(s).toLowerCase() !== 'general')
  )];
  console.log("📂 Subcategorías detectadas:", subcategorias);

  subcategorias.forEach(sub => {
    const btn = document.createElement('button');
    btn.textContent = sub;
    btn.className = 'btn-subgrupo';
    btn.addEventListener("click", (e) => mostrarSubgrupo(sub, e));
    panel.appendChild(btn);
    console.log("➕ Botón subgrupo creado:", sub);
  });

  renderPagina(1, productosGrupo);
  renderPaginacion(productosGrupo);

  if (subcategorias.length > 0) {
    if (!auto) {
      panel.classList.remove('oculta');
      console.log("📂 Panel subcategorias visible");
    } else {
      panel.classList.add('oculta');
      console.log("📂 Panel subcategorias oculto (auto)");
    }
  } else {
    panel.classList.add('oculta');
    console.log("📂 Grupo sin subcategorías");
  }

  console.log("✅ Productos renderizados con paginación en #productos");
  window.scrollTo({ top: 0, behavior: 'auto' });
}
window.mostrarGrupo = mostrarGrupo;

function filtrarSubcategoria(grupo, subgrupo) {
  console.log("🟨 filtrarSubcategoria llamada con:", { grupo, subgrupo });

  const cont = document.getElementById("productos");
  if (!cont) {
    console.warn("⚠️ No existe #productos en el DOM");
    return;
  }
  cont.innerHTML = "";

  const grupoCanon = String(grupo || "").trim();
  const subCanon = String(subgrupo || "").trim();
  console.log("🎯 Grupo canon:", grupoCanon, " | Subgrupo canon:", subCanon || `General_${grupoCanon}`);

  let productosFiltrados;
  if (subCanon) {
    productosFiltrados = window.todosLosProductos.filter(p =>
      String(p.grupo || "").toLowerCase() === grupoCanon.toLowerCase() &&
      String(p.subgrupo || "").toLowerCase() === subCanon.toLowerCase()
    );
  } else {
    const subgrupoGeneral = `General_${grupoCanon}`;
    productosFiltrados = window.todosLosProductos.filter(p =>
      String(p.grupo || "").toLowerCase() === grupoCanon.toLowerCase() &&
      String(p.subgrupo || "").toLowerCase() === subgrupoGeneral.toLowerCase()
    );
  }

  console.log("📦 Productos filtrados:", productosFiltrados.length);

  renderPagina(1, productosFiltrados);
  renderPaginacion(productosFiltrados);

  console.log("✅ Productos renderizados con paginación en #productos");
  console.log("📥 Hijos actuales en #productos:", cont.children.length);

  window.scrollTo({ top: 0, behavior: 'auto' });
}
window.filtrarSubcategoria = filtrarSubcategoria;

(function setupImmediate() {
  // Ocultar paneles si existen
  const panelSubcategorias = document.getElementById('panelSubcategorias');
  const panelGrupos = document.getElementById('panelGrupos');
  if (panelSubcategorias) panelSubcategorias.classList.add('oculta');
  if (panelGrupos) panelGrupos.classList.add('oculta');
  
  // Configurar carrito con reintento
  const toggleBtn = document.getElementById('toggleCarrito');
  if (toggleBtn) {
    toggleBtn.onclick = function() {
      const carritoDiv = document.getElementById('carrito');
      if (!carritoDiv) return;
      
      // Usar getComputedStyle para mayor precisión
      const isVisible = window.getComputedStyle(carritoDiv).display !== 'none';
      carritoDiv.style.display = isVisible ? 'none' : 'block';
    };
    console.log("✅ Carrito configurado inmediatamente");
  } else {
    // Si no existe, reintentar en 50ms
    setTimeout(setupImmediate, 50);
  }
})();  
    
let carrito = [];

function agregarAlCarritoDOM(nombre, idPrecioSpan, idCantidad, id_base, grupo = "", subgrupo = "") {
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
  
  const existente = carrito.find(item => 
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
      subgrupo 
    };
    carrito.push(nuevoItem);
  }
  
  actualizarCarrito();
  console.log(`✅ Producto agregado al carrito: ${nombre} ${talleElegido !== "unico" ? `(Talle: ${talleElegido})` : ""}`);
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

  fetch("https://mpagina.onrender.com/login-admin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, clave })
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === "ok" && data.token) {
        alert("✅ Acceso concedido");
        
        const loginToggleBtn = document.getElementById("loginToggleBtn");
        if (loginToggleBtn) {
          loginToggleBtn.style.display = "none";
        }
        
        const loginForm = document.getElementById("loginFloatingForm");
        if (loginForm) {
          loginForm.style.display = "none";
        }
        
        location.href = `index.html?token=${data.token}`;
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

function eliminarDelCarrito(id_base, talle, event) {
  if (event?.stopPropagation) event.stopPropagation();

  console.log("[CARRITO] ❌ Eliminando:", { id_base, talle });

  carrito = carrito.filter(p => {
    if (talle && talle !== "unico") {
      return !(p.id_base === id_base && p.talle === talle);
    } else {
      return p.id_base !== id_base;
    }
  });

  actualizarCarrito();
}
    
function mostrarSubgrupo(subgrupo, event) {
  console.log("🟩 mostrarSubgrupo llamada con:", subgrupo);

  const grupoActivoBtn = document.querySelector('.btn-grupo.active');
  const grupoActivo = grupoActivoBtn ? grupoActivoBtn.textContent.trim() : null;
  console.log("🎯 Grupo activo detectado:", grupoActivo);

  if (!grupoActivo) {
    console.warn("⚠️ No hay grupo activo para mostrar subgrupo:", subgrupo);
    return;
  }

  document.querySelectorAll('.btn-subgrupo').forEach(btn => btn.classList.remove('active'));
  if (event?.target) {
    event.target.classList.add('active');
    console.log("👉 Botón subgrupo marcado:", event.target.textContent);
  }

  const grupoCanon = String(grupoActivo).trim();
  const subCanon = String(subgrupo || "").trim();

  window.currentGrupo = grupoCanon.toLowerCase();
  window.currentSub = subCanon.toLowerCase();
  console.log("📌 Estado canónico actualizado:", { currentGrupo: window.currentGrupo, currentSub: window.currentSub });

  console.log("➡️ Llamando a filtrarSubcategoria con:", { grupoCanon, subCanon });
  filtrarSubcategoria(grupoCanon, subCanon);

  const cont = document.getElementById("productos");
  if (cont) {
    console.log("📥 Hijos actuales en #productos después de mostrarSubgrupo:", cont.children.length);
    console.log("🧩 HTML actual de #productos:", cont.innerHTML.slice(0, 300) + "...");
    const style = window.getComputedStyle(cont);
    console.log("👁️ Estilo de #productos:", { display: style.display, visibility: style.visibility });
  }
}
window.mostrarSubgrupo = mostrarSubgrupo;

function actualizarPrecioEnCarrito(nombre, nuevoPrecio) {
  let cambio = false;
  carrito.forEach(item => {
    if (item.nombre === nombre && item.precio !== nuevoPrecio) {
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
      const precioActual = parseFloat(precioSpan.textContent);
      if (!isNaN(precioActual)) {
        item.precio = precioActual;
      }
    }
  });
}

function actualizarCarrito() {
  sincronizarPreciosDelCarrito();

  const lista = document.getElementById('listaCarrito');
  const totalSpan = document.getElementById('totalCarrito');
  if (!lista || !totalSpan) return;

  lista.innerHTML = '';
  let suma = 0;

  if (carrito.length === 0) {
    lista.innerHTML = "<li>🛒 Carrito vacío</li>";
    totalSpan.textContent = "0.00";
    return;
  }

  const fmt = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  carrito.forEach(item => {
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
        <button onmousedown="eliminarDelCarrito('${item.id_base}', '${item.talle}', '${item.color}', event)" 
                style="background: none; border: none; color: red; font-weight: bold; font-size: 16px; cursor: pointer;">
          ❌
        </button>
      </li>`);
  });

  totalSpan.textContent = fmt.format(suma);
}

function mostrarTodos() {
  const panelGrupos = document.getElementById('panelGrupos');
  const panelSub = document.getElementById('panelSubcategorias');

  if (!panelGrupos || !panelSub) return;

  panelGrupos.classList.toggle('oculta');

  if (!panelSub.classList.contains('oculta')) {
    panelSub.classList.add('oculta');
  }
}
window.mostrarTodos = mostrarTodos; 
      
function irAContacto() {
  const contacto = document.getElementById('ubicacion');
  if (contacto) contacto.scrollIntoView({ behavior: 'smooth' });
}
window.irAContacto = irAContacto; 
    
function renderProducto(p, esLCP = false) {
  console.log("🎯 [RENDER-PRODUCTO] INICIO =====================================");
  console.log("📦 Datos completos del producto recibido:", JSON.stringify(p, null, 2));
  
  const card = document.createElement("div");
  card.className = "col-lg-4 col-md-6 col-sm-12 mb-4 fade-reorder card-producto";
  card.dataset.id = p.id_base;
  card.dataset.precio = p.precio;
  console.log("💰 [PRECIO-ANTERIOR] Verificación:");
  console.log("   - ID Producto:", p.id_base);
  console.log("   - Nombre:", p.nombre);
  console.log("   - Precio actual (p.precio):", p.precio, "(tipo:", typeof p.precio, ")");
  console.log("   - Precio anterior (p.precio_anterior):", p.precio_anterior, "(tipo:", typeof p.precio_anterior, ")");
  console.log("   - ¿Existe campo precio_anterior?:", "precio_anterior" in p);
  console.log("   - Valor directo:", p.precio_anterior);
  console.log("   - Valor parseado:", parseFloat(p.precio_anterior));

  const precioActual = parseFloat(p.precio) || 0;
  const precioAnterior = parseFloat(p.precio_anterior) || 0;
  
  console.log("   - Precio actual (parseado):", precioActual);
  console.log("   - Precio anterior (parseado):", precioAnterior);

  const esOferta = precioAnterior > 0 && precioAnterior > precioActual;
  const descuentoPorcentaje = esOferta ? 
    Math.round(((precioAnterior - precioActual) / precioAnterior) * 100) : 0;
  
  console.log("   - ¿Es oferta?:", esOferta, "(precioAnterior > precioActual:", precioAnterior > precioActual, ")");
  console.log("   - Porcentaje descuento:", descuentoPorcentaje + "%");
  console.log("   - Ahorro: $" + (precioAnterior - precioActual).toFixed(2));

  if (!esOferta && window.todosLosProductos) {
    console.log("   🔍 Buscando precio anterior en array global...");
    const productoCompleto = window.todosLosProductos.find(prod => prod.id_base === p.id_base);
    if (productoCompleto) {
      console.log("   - Producto encontrado en array global:", productoCompleto.nombre);
      console.log("   - precio_anterior en array:", productoCompleto.precio_anterior);
      if (productoCompleto.precio_anterior && productoCompleto.precio_anterior > precioActual) {
        console.log("   ⚠️ ¡OFERTA ENCONTRADA EN ARRAY GLOBAL!");
        console.log("   - Usando precio anterior del array:", productoCompleto.precio_anterior);
        precioAnterior = parseFloat(productoCompleto.precio_anterior) || 0;
        esOferta = precioAnterior > 0 && precioAnterior > precioActual;
      }
    }
  }
  
  console.log("   - Resultado final - Es oferta:", esOferta);
  console.log("   - Precio anterior final:", precioAnterior);
  
  const tieneStockPorTalle = p.stock_por_talle && Object.keys(p.stock_por_talle).length > 0;
  
  console.log("📦 [STOCK] Verificación:");
  console.log("   - Tiene stock_por_talle:", tieneStockPorTalle);
  console.log("   - stock_por_talle:", p.stock_por_talle);
  console.log("   - stock:", p.stock);
  
  let stockData = {};
  let opcionesTalles = "";
  let talleInicial = "";
  let stockInicial = 0;
  
  if (tieneStockPorTalle) {
    stockData = p.stock_por_talle;
    window[`stock_por_talle_${p.id_base}`] = stockData;
    
    console.log("   - Stock por talle asignado:", stockData);

    const tallesDisponibles = Object.keys(stockData);
    console.log("   - Talles disponibles:", tallesDisponibles);
    
    tallesDisponibles.forEach(talle => {
      const stock = stockData[talle] || 0;
      console.log(`   - Talle ${talle}: stock = ${stock}`);
      
      const opcion = stock > 0 ? 
        `<option value="${talle}">${talle} (${stock} disponible${stock > 1 ? 's' : ''})</option>` :
        `<option value="${talle}" disabled>${talle} (Agotado)</option>`;
      opcionesTalles += opcion;
    
      if (stockInicial === 0 && stock > 0) {
        stockInicial = stock;
        talleInicial = talle;
        console.log(`   - Talle inicial elegido: ${talleInicial} (stock: ${stockInicial})`);
      }
    });

    if (stockInicial === 0 && tallesDisponibles.length > 0) {
      talleInicial = tallesDisponibles[0];
      stockInicial = stockData[talleInicial] || 0;
      console.log(`   - Sin stock, usando primer talle: ${talleInicial} (stock: ${stockInicial})`);
    }
  } else {
    const stockGeneral = p.stock || 0;
    stockData = { "unico": stockGeneral };
    window[`stock_por_talle_${p.id_base}`] = stockData;
    stockInicial = stockGeneral;
    console.log(`   - Producto sin talles, stock general: ${stockGeneral}`);
  }
  
  const mostrarStock = stockInicial > 0 ? stockInicial : "Sin stock";
  const claseStock = stockInicial > 0 ? "" : "text-danger";
  
  console.log("   - Stock inicial final:", stockInicial);
  console.log("   - Talle inicial final:", talleInicial);

  const nombreEscapado = p.nombre.replace(/'/g, "\\'").replace(/"/g, '\\"');
  const descripcionEscapada = (p.descripcion || "").replace(/'/g, "\\'").replace(/"/g, '\\"');
  const imagenUrl = p.imagen_url || '/static/img/fallback.webp';
  const grupoEscapado = (p.grupo || "").replace(/'/g, "\\'");
  const subgrupoEscapado = (p.subgrupo || "").replace(/'/g, "\\'");

  const fotosAdicionalesSeguras = (p.fotos_adicionales || []).map(foto => 
    foto.replace(/'/g, "\\'").replace(/"/g, '\\"')
  );
  
  console.log("🔗 [URLs] Verificación:");
  console.log("   - Imagen URL:", imagenUrl);
  console.log("   - Fotos adicionales:", fotosAdicionalesSeguras.length);
  
  const onclickAgregar = `agregarAlCarritoDOM('${nombreEscapado}', 'precio_${p.id_base}', 'cantidad_${p.id_base}', '${p.id_base}', '${grupoEscapado}', '${subgrupoEscapado}')`;
  
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
        ${fotosAdicionalesSeguras.slice(0, 3).map((foto, idx) => `
          <img src="${foto}" 
               alt="Foto ${idx+1}" 
               style="width: 40px; height: 40px; object-fit: cover; border-radius: 3px; cursor: pointer;"
               onclick="openModal('${foto}')">
        `).join('')}
        ${fotosAdicionalesSeguras.length > 3 ? `<span class="ms-1 text-muted">+${fotosAdicionalesSeguras.length - 3}</span>` : ''}
      </div>
    </div>
  ` : '';
  
  console.log("🎨 [HTML] Generando HTML para producto:", p.nombre);
  console.log("   - Es oferta en HTML:", esOferta);
  console.log("   - Badge oferta generado:", esOferta ? "SÍ" : "NO");
  console.log("   - Precio anterior en HTML:", precioAnterior);
  console.log("   - Precio actual en HTML:", precioActual);
  
  // Construir atributos de la imagen según si es LCP o no
  const imgSrc = `${imagenUrl}${imagenUrl.includes('?') ? '&' : '?'}format=webp`;
  let imgAttributes = `src="${imgSrc}"`;
  if (!esLCP) {
      imgAttributes += ` data-src="${imagenUrl}" loading="lazy"`;
  } else {
      imgAttributes += ` loading="eager" fetchpriority="high"`;
  }
  
  card.innerHTML = `
  <div class="card-giratoria">
    <div class="card-contenedor">
      <!-- FRENTE (COMPLETO) -->
      <div class="card-front">
        <!-- 🔥 ETIQUETA OFERTA SIMPLE - SOLO ADELANTE -->
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
             style="width:100%; height:180px; object-fit:contain; border-radius:4px; cursor:pointer; opacity:0; transition: opacity 0.3s;"
             class="lazy-image"
             onload="this.style.opacity='1'"
             onclick="openModal('${imagenUrl}')">
        <div class="card-body">
          <h5 class="card-title" style="font-size: 1.1rem !important;">${p.nombre}</h5>
          
          <p class="mb-2">
            <strong>Precio:</strong> 
            <!-- 🔥 PRECIO ANTERIOR TACHADO (SOLO SI HAY OFERTA) -->
            ${esOferta ? `
              <span style="text-decoration: line-through; color: #999; font-size: 0.9rem; margin-right: 5px;">
                $${precioAnterior.toFixed(2)}
              </span>
            ` : ''}
            <!-- 🔥 PRECIO ACTUAL EN ROJO SI ES OFERTA -->
            $<span id="precio_${p.id_base}" style="${esOferta ? 'color: #ff4757; font-weight: bold;' : ''}">${p.precio}</span>
            ${esOferta ? `<small style="color: #20c997; font-weight: bold; margin-left: 5px;">Ahorras $${(precioAnterior - precioActual).toFixed(2)}</small>` : ''}
          </p>
          
          ${Object.keys(stockData).length > 0 && Object.keys(stockData)[0] !== "unico" ? `
  <div class="mb-2 d-flex align-items-center gap-2">
    <label class="mb-0"><strong>Talle:</strong></label>
    <select id="talle_${p.id_base}" class="form-select form-select-sm w-auto"
            onchange="actualizarStockPorTalle('${p.id_base}', this.value)"
            style="min-width: 80px; max-width: 160px;">
      <option value="">-</option>
      ${opcionesTalles}
    </select>
  </div>
` : ""}
          
          <div class="mt-3 d-flex align-items-center gap-2">
            <input type="number" min="1" max="${stockInicial > 0 ? stockInicial : 1}" value="1"
                   id="cantidad_${p.id_base}"
                   class="form-control form-control-sm" style="width: 70px;"
                   ${stockInicial <= 0 ? "disabled" : ""}>
            
            <button type="button" class="btn btn-secondary btn-sm" id="btn_agregar_${p.id_base}"
              onclick="${onclickAgregar}"
              ${stockInicial <= 0 ? "disabled style='opacity:0.5'" : ""}>
              ${stockInicial > 0 ? "Agregar al carrito" : "❌ Sin stock"}
            </button>
          </div>
          
          <!-- 🔥 FOTOS ADICIONALES (SIN TEXTO) -->
          ${fotosAdicionalesHTML}
          
          <!-- 🔥 BOTÓN WHATSAPP ESPECÍFICO -->
          ${whatsappUrl ? `
            <div class="mt-3">
              <a href="${whatsappUrl}" class="btn btn-whatsapp btn-sm w-100 d-flex align-items-center justify-content-center gap-2" target="_blank" style="background-color: #0c6909; color: white;">
                <img src="/static/img/whatsapp.png" alt="WhatsApp" style="width: 20px; height: 20px;">
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
        
        <!-- 🔥 ÁREA DE DESCRIPCIÓN (OCUPA TODO EL ESPACIO DISPONIBLE) -->
        <div class="descripcion-area" style="
          flex: 1;
          padding: 80px 80px 80px 80px;
          overflow-y: auto;
          text-align: center;
          flex-direction: column;
          justify-content: center;
          /* 🔥 OCULTAR BARRA DE SCROLL PERO PERMITIR SCROLL */
          scrollbar-width: none; /* Firefox */
          -ms-overflow-style: none; /* IE/Edge */
        ">
          <div class="descripcion-area::-webkit-scrollbar {
            display: none; /* Chrome/Safari/Opera */
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
        
        <!-- 🔥 SECCIÓN INFERIOR (FUERA DEL ÁREA DE DESCRIPCIÓN) -->
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
          
          <!-- 🔥 REMOVIDO: Sección de oferta en el reverso -->
          
          <div class="mt-2">
            <button class="btn btn-secondary btn-sm w-100" onclick="girarCard(this)">
              🔄 Volver al frente
            </button>
          </div>
          
          ${window.modoAdmin ? `
            <div class="mt-2 d-flex gap-2">
              <button type="button" class="btn btn-warning btn-sm w-50"
                onclick="cargarProductoCompletoParaEditar('${p.id_base}')">
                ✏️ Editar
              </button>
              <button type="button" class="btn btn-danger btn-sm w-50"
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

  console.log("✅ [RENDER-PRODUCTO] HTML generado para:", p.nombre);
  console.log("   - Badge visible en DOM:", esOferta ? "SÍ (debería verse)" : "NO");
  console.log("   - Card añadida al DOM");
  console.log("🎯 [RENDER-PRODUCTO] FIN ======================================\n\n");

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
    
function obtenerCarrito() {
  console.log("🛒 [obtenerCarrito] Mapeando carrito a formato MP:");
  
  return carrito.map(item => {
    console.log("  - Item original:", item);
    
    let precio = item.precio;
    if (typeof precio === 'string') {
      precio = parseFloat(precio.replace(/[$,]/g, '').trim());
      console.log(`  - Precio convertido de "${item.precio}" a ${precio}`);
    } else if (typeof precio === 'number') {
      console.log(`  - Precio ya es número: ${precio}`);
    } else {
      precio = 0;
      console.warn(`  - ⚠️ Precio no válido: ${precio}, usando 0`);
    }
    
    let cantidad = parseInt(item.cantidad) || 1;
    
    const itemFormateado = {
      title: item.nombre + (item.talle ? ` (${item.talle})` : ""),
      quantity: cantidad,
      unit_price: precio,
      id_base: item.id_base,
      grupo: item.grupo || "",
      subgrupo: item.subgrupo || "",
      nombre: item.nombre,
      precio: precio, 
      cantidad: cantidad,
      talle: item.talle || ""
    };
    
    console.log("  - Item formateado para MP:", itemFormateado);
    return itemFormateado;
  });
}
    
function ajustarPosicionesPaneles() {
  const panelGrupos = document.getElementById('panelGrupos');
  const panelSub = document.getElementById('panelSubcategorias');
  const barraNav = document.querySelector('.barra-navegacion');

  if (!panelGrupos || !panelSub) {
    console.warn("⚠️ No existen paneles en el DOM");
    return;
  }

  console.log("🔧 ajustando posiciones de paneles...");

  if (!panelGrupos.classList.contains('oculta')) {
    const alturaBarra = barraNav ? barraNav.offsetHeight : 0;
    panelGrupos.style.top = alturaBarra + 'px';
    panelGrupos.style.position = 'fixed';
    panelGrupos.style.left = '0';
    panelGrupos.style.right = '0';
    console.log("📐 Panel grupos → top:", panelGrupos.style.top, "alturaBarra:", alturaBarra);
  }

  if (!panelSub.classList.contains('oculta')) {
    const alturaBarra = barraNav ? barraNav.offsetHeight : 0;
    const alturaGrupos = panelGrupos ? panelGrupos.offsetHeight : 0;
    const margenAdicional = 19;
    const desplazamientoArriba = -20;
    const topCalc = alturaBarra + alturaGrupos + margenAdicional + desplazamientoArriba;
    panelSub.style.top = '92px';
    panelSub.style.position = 'fixed';
    panelSub.style.left = '0';
    panelSub.style.right = '0';
    console.log("📐 Panel subcategorias → top:", panelSub.style.top, 
                "alturaBarra:", alturaBarra, "alturaGrupos:", alturaGrupos);
  } else {
    panelSub.style.top = '';
    console.log("📂 Panel subcategorias oculto");
  }

  const styleGrupos = window.getComputedStyle(panelGrupos);
  const styleSub = window.getComputedStyle(panelSub);
  console.log("👁️ Estilo panelGrupos:", { display: styleGrupos.display, top: styleGrupos.top });
  console.log("👁️ Estilo panelSub:", { display: styleSub.display, top: styleSub.top });
}
    
function ordenarGrupo(valor) {
  console.log("🔄 ordenarGrupo llamada con:", valor);

  const cont = document.getElementById("productos");
  if (!cont) return;

  const grupoCanon = window.currentGrupo;
  const subCanon = window.currentSub;

  let productosFiltrados = window.todosLosProductos.filter(p =>
    String(p.grupo || "").toLowerCase() === grupoCanon.toLowerCase() &&
    String(p.subgrupo || "").toLowerCase() === subCanon.toLowerCase()
  );

  productosFiltrados.sort((a, b) => {
    const pa = Number(a.precio) || 0;
    const pb = Number(b.precio) || 0;
    return valor === "asc" ? pa - pb : pb - pa;
  });
  console.log("📊 Productos ordenados:", valor, productosFiltrados);

  cont.innerHTML = "";

  const grupoDiv = document.createElement("div");
  grupoDiv.className = "grupo-section";
  grupoDiv.innerHTML = `<h3>${grupoCanon}</h3>`;

  const subDiv = document.createElement("div");
  subDiv.className = "subgrupo-bloque";
  subDiv.innerHTML = `<h4>${subCanon}</h4>`;

  productosFiltrados.forEach(p => {
    const card = renderProducto(p);
    subDiv.appendChild(card);

    requestAnimationFrame(() => card.classList.add("show"));
    setTimeout(() => card.classList.remove("fade-reorder"), 50);

    console.log("🛒 Card insertada en subgrupo:", p.nombre);
  });

  grupoDiv.appendChild(subDiv);
  cont.appendChild(grupoDiv);
  console.log("✅ Bloque renderizado en ordenarGrupo, hijos finales:", cont.children.length);
}

window.ordenarGrupo = ordenarGrupo;

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
  mensaje.style.webkitBackdropFilter = 'blur(10px)';
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

document.getElementById("btnQuitarFoto").addEventListener("click", () => {
  document.getElementById("inputFoto").value = "";
  const imgPreview = document.getElementById("previewFoto");
  imgPreview.src = "";
  imgPreview.classList.add("d-none");

  document.getElementById("btnQuitarFoto").classList.add("d-none");
  window.fotoOptimizada = null;

  console.log("🗑️ Foto eliminada");
}); 
