window.fotoOptimizada = null;
window.fotosAdicionalesExistentes = null;
window.productoEditandoId = null;

const formImages = new Map(); 

function editarProductoDesdeCard(id_base) {
  const productoOriginal = window.todosLosProductos?.find(p => p.id_base === id_base);
  if (!productoOriginal) {
    alert("❌ Producto no encontrado");
    return;
  }
  const container = document.getElementById('adminFormsContainer');
  if (container) container.classList.remove('d-none');
  crearFormulario(productoOriginal, { esEdicion: true }); // ✅ CORREGIDO
}

function generarFormId() {
  return 'form_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function crearFormulario(producto = null, opciones = {}) {
  const { esEdicion = false } = opciones;
  const template = document.getElementById('productFormTemplate');
  const clone = template.content.cloneNode(true);
  const formDiv = clone.querySelector('.admin-card');
  const formId = generarFormId();
  formDiv.dataset.formId = formId;
  if (esEdicion && producto?.id_base) {
    formDiv.dataset.idBase = producto.id_base; 
  }
  const estadoImagenes = { fotoOptimizada: null, fotosAdicionales: [] };
  if (esEdicion && producto) {
    if (producto.imagen_url) {
      estadoImagenes.imagenExistente = producto.imagen_url;
    }
    if (producto.fotos_adicionales && producto.fotos_adicionales.length) {
      estadoImagenes.fotosExistentes = producto.fotos_adicionales.slice(); 
    }
  }
  formImages.set(formId, estadoImagenes);

  if (producto) {
    rellenarFormulario(formDiv, producto, esEdicion); 
  }
  configurarEventosFormulario(formDiv);
  document.getElementById('formsList').appendChild(formDiv);
}

function rellenarFormulario(formDiv, producto, esEdicion = false) {
  formDiv.querySelector('.nombreProd').value = producto.nombre || '';
  formDiv.querySelector('.precioProd').value = producto.precio || '';
  formDiv.querySelector('.descripcionProd').value = producto.descripcion || '';
  formDiv.querySelector('.grupoProd').value = producto.grupo || '';
  formDiv.querySelector('.subgrupoProd').value = producto.subgrupo || '';
  formDiv.querySelector('.tallesProd').value = producto.talles ? producto.talles.join(', ') : '';

  const tallesArray = producto.talles || [];
  const stockSimple = formDiv.querySelector('.stockSimple');
  const stockPorTalleContainer = formDiv.querySelector('.stockPorTalleContainer');
  const stockGeneral = formDiv.querySelector('.stockGeneral');
  const stockPorTalleInput = formDiv.querySelector('.stockPorTalle');

  if (tallesArray.length > 0) {
    stockSimple.style.display = 'none';
    stockPorTalleContainer.style.display = 'block';
    if (producto.stock_por_talle) {
      const stockStr = Object.entries(producto.stock_por_talle)
        .map(([t, s]) => `${t}:${s}`).join(', ');
      stockPorTalleInput.value = stockStr;
    } else {
      stockPorTalleInput.value = tallesArray.map(t => `${t}:0`).join(', ');
    }
  } else {
    stockSimple.style.display = 'block';
    stockPorTalleContainer.style.display = 'none';
    stockGeneral.value = producto.stock || 0;
  }
  if (esEdicion) {
    const formId = formDiv.dataset.formId;
    const images = formImages.get(formId);
    const previewFoto = formDiv.querySelector('.previewFoto');
    const btnQuitarFoto = formDiv.querySelector('.btnQuitarFoto');
    const previewAdicionales = formDiv.querySelector('.previewFotosAdicionales');

    if (producto.imagen_url) {
      previewFoto.src = producto.imagen_url;
      previewFoto.classList.remove('d-none');
      btnQuitarFoto.classList.remove('d-none');
    }
    if (producto.fotos_adicionales && producto.fotos_adicionales.length) {
      producto.fotos_adicionales.forEach((url, index) => {
        const miniaturaDiv = document.createElement('div');
        miniaturaDiv.style.position = 'relative';
        miniaturaDiv.style.display = 'inline-block';
        const id = 'existente_' + index + '_' + Date.now();
        miniaturaDiv.dataset.id = id;

        const img = document.createElement('img');
        img.src = url;
        img.style.width = '60px';
        img.style.height = '60px';
        img.style.objectFit = 'cover';
        img.style.margin = '3px';
        img.style.borderRadius = '4px';

        const btnEliminar = document.createElement('button');
        btnEliminar.textContent = '✖';
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
        btnEliminar.style.fontSize = '12px';
        btnEliminar.style.fontWeight = 'bold';
        btnEliminar.style.display = 'flex';
        btnEliminar.style.alignItems = 'center';
        btnEliminar.style.justifyContent = 'center';
        btnEliminar.style.lineHeight = '1';

        btnEliminar.onclick = (e) => {
          e.stopPropagation();
          const id = miniaturaDiv.dataset.id;
          if (images.fotosExistentes) {
            const index = images.fotosExistentes.indexOf(url);
            if (index !== -1) images.fotosExistentes.splice(index, 1);
          }
          miniaturaDiv.remove();
        };

        miniaturaDiv.appendChild(img);
        miniaturaDiv.appendChild(btnEliminar);
        previewAdicionales.appendChild(miniaturaDiv);
      });
    }
  }
}

function configurarEventosFormulario(formDiv) {
  const formId = formDiv.dataset.formId;
  const images = formImages.get(formId);

  if (!images.fotosAdicionales) {
    images.fotosAdicionales = [];
  }

  const inputFoto = formDiv.querySelector('.inputFoto');
  const previewFoto = formDiv.querySelector('.previewFoto');
  const btnQuitarFoto = formDiv.querySelector('.btnQuitarFoto');

  inputFoto.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const blobOptimizado = await optimizarImagen(file);
      images.fotoOptimizada = blobOptimizado;
      const urlPreview = URL.createObjectURL(blobOptimizado);
      previewFoto.src = urlPreview;
      previewFoto.classList.remove('d-none');
      btnQuitarFoto.classList.remove('d-none');
    } catch (err) {
      alert('❌ No se pudo optimizar la imagen');
    }
  });

  btnQuitarFoto.addEventListener('click', () => {
    if (images.fotoOptimizada) {
      URL.revokeObjectURL(previewFoto.src);
    }
    inputFoto.value = '';
    previewFoto.src = '';
    previewFoto.classList.add('d-none');
    btnQuitarFoto.classList.add('d-none');
    images.fotoOptimizada = null;
  });

  const fotosAdicionalesInput = formDiv.querySelector('.fotosAdicionales');
  const previewAdicionales = formDiv.querySelector('.previewFotosAdicionales');

  fotosAdicionalesInput.addEventListener('change', async (e) => {
    const files = Array.from(e.target.files);
    for (const file of files) {
      try {
        const blob = await optimizarImagen(file);
        const id = Date.now() + '-' + Math.random().toString(36).substr(2, 9); 
        const url = URL.createObjectURL(blob);

        images.fotosAdicionales.push({ id, blob, url });
 
        const miniaturaDiv = document.createElement('div');
        miniaturaDiv.style.position = 'relative';
        miniaturaDiv.style.display = 'inline-block';
        miniaturaDiv.dataset.id = id;
        
        const img = document.createElement('img');
        img.src = url;
        img.style.width = '60px';
        img.style.height = '60px';
        img.style.objectFit = 'cover';
        img.style.margin = '3px';
        img.style.borderRadius = '4px';
        
        const btnEliminar = document.createElement('button');
        btnEliminar.textContent = '✖';
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
        btnEliminar.style.fontSize = '12px';
        btnEliminar.style.fontWeight = 'bold';
        btnEliminar.style.display = 'flex';
        btnEliminar.style.alignItems = 'center';
        btnEliminar.style.justifyContent = 'center';
        btnEliminar.style.lineHeight = '1';

        btnEliminar.onclick = (e) => {
          e.stopPropagation();
          const id = miniaturaDiv.dataset.id;
          const index = images.fotosAdicionales.findIndex(f => f.id === id);
          if (index !== -1) {
            URL.revokeObjectURL(images.fotosAdicionales[index].url);
            images.fotosAdicionales.splice(index, 1);
          }
          miniaturaDiv.remove();
        };
        
        miniaturaDiv.appendChild(img);
        miniaturaDiv.appendChild(btnEliminar);
        previewAdicionales.appendChild(miniaturaDiv);
        
      } catch (err) {
        console.warn('Error al optimizar foto adicional', err);
      }
    }
    fotosAdicionalesInput.value = '';
  });

  const tallesInput = formDiv.querySelector('.tallesProd');
  const stockSimpleDiv = formDiv.querySelector('.stockSimple');
  const stockPorTalleDiv = formDiv.querySelector('.stockPorTalleContainer');
  const stockPorTalleInput = formDiv.querySelector('.stockPorTalle');

  tallesInput.addEventListener('input', () => {
    const talles = tallesInput.value.split(',').map(t => t.trim()).filter(Boolean);
    if (talles.length > 0) {
      stockSimpleDiv.style.display = 'none';
      stockPorTalleDiv.style.display = 'block';
      if (!stockPorTalleInput.value.trim()) {
        stockPorTalleInput.value = talles.map(t => `${t}:0`).join(', ');
      }
    } else {
      stockSimpleDiv.style.display = 'block';
      stockPorTalleDiv.style.display = 'none';
    }
  });

  formDiv.querySelector('.duplicar-btn').addEventListener('click', async () => {
    const productoActual = await obtenerDatosFormulario(formDiv, false); 
    crearFormulario(productoActual);
  });

  formDiv.querySelector('.eliminar-btn').addEventListener('click', () => {
    if (confirm('¿Eliminar este formulario?')) {
      const images = formImages.get(formId);
      if (images.fotoOptimizada) {
        URL.revokeObjectURL(previewFoto.src);
      }
      images.fotosAdicionales.forEach(item => {
        URL.revokeObjectURL(item.url);
      });
      formImages.delete(formId);
      formDiv.remove();
    }
  });

  formDiv.querySelector('.guardar-this').addEventListener('click', async () => {
  const producto = await obtenerDatosFormulario(formDiv, true);
  const exito = await guardarProducto(producto, formDiv);
  if (exito) {
    if (images.fotoOptimizada) {
      URL.revokeObjectURL(previewFoto.src);
    }
    images.fotosAdicionales.forEach(item => URL.revokeObjectURL(item.url));
    formImages.delete(formId);
    formDiv.remove();
    }
  });
}  

async function obtenerDatosFormulario(formDiv, incluirImagenes = false) {
  const formId = formDiv.dataset.formId;
  const images = formImages.get(formId);
  const producto = {
    nombre: formDiv.querySelector('.nombreProd').value.trim(),
    precio: parseFloat(formDiv.querySelector('.precioProd').value),
    descripcion: formDiv.querySelector('.descripcionProd').value.trim(),
    grupo: formDiv.querySelector('.grupoProd').value.trim() || 'General',
    subgrupo: formDiv.querySelector('.subgrupoProd').value.trim() || 'general',
    talles: formDiv.querySelector('.tallesProd').value.split(',').map(t => t.trim()).filter(Boolean)
  };
  const stockSimpleDiv = formDiv.querySelector('.stockSimple');
  if (stockSimpleDiv.style.display !== 'none') {
    producto.stock = parseInt(formDiv.querySelector('.stockGeneral').value) || 0;
  } else {
    const stockPorTalleInput = formDiv.querySelector('.stockPorTalle');
    const stockPorTalle = {};
    stockPorTalleInput.value.split(',').forEach(item => {
      const [talle, stock] = item.split(':').map(s => s.trim());
      if (talle && stock) stockPorTalle[talle] = parseInt(stock) || 0;
    });
    producto.stock_por_talle = stockPorTalle;
  }

  if (incluirImagenes) {
    if (images.fotoOptimizada) {
      producto.imagen_url = await subirImagen(images.fotoOptimizada);
    } else if (images.imagenExistente) {
      producto.imagen_url = images.imagenExistente; 
    } else {
      producto.imagen_url = null;
    }
    producto.fotos_adicionales = [];
    if (images.fotosExistentes && images.fotosExistentes.length) {
      producto.fotos_adicionales.push(...images.fotosExistentes);
    }
    if (images.fotosAdicionales.length > 0) {
      for (const item of images.fotosAdicionales) {
        const url = await subirImagen(item.blob);
        producto.fotos_adicionales.push(url);
      }
    }
  }
  return producto;
}

async function subirImagen(blob) {
  const formData = new FormData();
  formData.append('file', blob, 'imagen.webp');
  formData.append('email', window.cliente.email);
  const resp = await fetch('https://mpagina.onrender.com/subir-foto', {
    method: 'POST',
    body: formData
  });
  const data = await resp.json();
  if (data.ok && data.url) return data.url;
  throw new Error('Error al subir imagen');
}

async function guardarProducto(producto, formDiv) {
  const email = window.cliente?.email;
  if (!email) {
    alert("❌ No hay email de admin, no se puede guardar");
    return false;
  }

  const idBase = formDiv?.dataset.idBase;
  const esEdicion = !!idBase;

  const payload = {
    producto: producto,
    email: email,
    es_edicion: esEdicion
  };
  if (esEdicion) {
    payload.producto.id_base = idBase;
  }

  try {
    const resp = await fetch("https://mpagina.onrender.com/guardar-producto", {
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
      console.log("✅ Producto guardado:", data);
      if (typeof mostrarToast === 'function') {
        mostrarToast(`✅ ${producto.nombre} guardado`);
      }
      return true;
    } else {
      throw new Error(data.error || data.message || "Error al guardar producto");
    }
  } catch (err) {
    console.error("❌ Error guardando producto:", err);
    alert("❌ Error: " + err.message);
    return false;
  }
}

if (window.modoAdmin) {
  const container = document.getElementById('adminFormsContainer');
  if (container) container.classList.remove('d-none');

  const logoutWrapper = document.getElementById('logoutAdminWrapper');
  if (logoutWrapper) logoutWrapper.style.display = 'block';

  const configMP = document.getElementById('configurarMP');
  if (configMP) configMP.classList.remove('d-none');
}

document.getElementById('nuevoFormBtn').addEventListener('click', () => {
  crearFormulario();
});

document.getElementById('guardarTodosBtn').addEventListener('click', async () => {
  const forms = document.querySelectorAll('#formsList .admin-card');
  let okCount = 0;
  let errorCount = 0;

  for (const form of forms) {
    try {
      const producto = await obtenerDatosFormulario(form, true);
      const exito = await guardarProducto(producto, form);
      if (exito) {
        okCount++;
      } else {
        errorCount++;
      }
    } catch (err) {
      errorCount++;
    }
  }

  if (errorCount === 0) {
    forms.forEach(form => {
      const formId = form.dataset.formId;
      const images = formImages.get(formId);
      if (images) {
        if (images.fotoOptimizada) {
          const previewFoto = form.querySelector('.previewFoto');
          if (previewFoto.src) URL.revokeObjectURL(previewFoto.src);
        }
        images.fotosAdicionales.forEach(item => URL.revokeObjectURL(item.url));
        formImages.delete(formId);
      }
      form.remove();
    });
    alert(`✅ ${okCount} productos guardados correctamente.`);
  } else {
    alert(`✅ ${okCount} productos guardados, ❌ ${errorCount} errores. Revisa los que fallaron.`);
  }
});

function duplicarProductoDesdeCard(id_base) {
  const productoOriginal = window.todosLosProductos?.find(p => p.id_base === id_base);
  if (!productoOriginal) {
    alert("❌ Producto no encontrado");
    return;
  }
  const container = document.getElementById('adminFormsContainer');
  if (container) container.classList.remove('d-none');
  const copia = {
    nombre: productoOriginal.nombre,
    precio: productoOriginal.precio,
    descripcion: productoOriginal.descripcion,
    grupo: productoOriginal.grupo,
    subgrupo: productoOriginal.subgrupo,
    talles: productoOriginal.talles,
    stock_por_talle: productoOriginal.stock_por_talle,
    stock: productoOriginal.stock
  };
  crearFormulario(copia); 
}

function abrirConfigMercadoPago() {
    console.log("⚙️ Redirigiendo a configuración de Mercado Pago...");
    const urlRetorno = window.location.href;
    const configUrl = `${window.URL_BACKEND}/conectar_mp?email=${encodeURIComponent(window.cliente.email)}&url_retorno=${encodeURIComponent(urlRetorno)}`;
    window.location.href = configUrl;
}

async function eliminarProducto(id_base) {
  console.log("[ELIMINAR_PRODUCTO] 🔔 Click en botón eliminar → id_base:", id_base);
  try {
    const resp = await fetch("https://mpagina.onrender.com/eliminar-producto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_base, email: window.cliente.email })
    });
    const data = await resp.json();
    if (data.status === "ok") {
      const card = document.querySelector(`[data-id="${id_base}"]`);
      if (card) card.remove();
    } else {
      alert("Error al eliminar producto: " + data.error);
    }
  } catch (err) {
    alert("Error al eliminar producto: " + err.message);
  }
}

async function optimizarImagen(file) {
  console.log(`📂 [optimizarImagen] Iniciando optimización: ${file.name} (${file.size} bytes)`);
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

document.getElementById("inputFoto")?.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const blobOptimizado = await optimizarImagen(file);
    window.fotoOptimizada = blobOptimizado;
    const urlPreview = URL.createObjectURL(blobOptimizado);
    const imgPreview = document.getElementById("previewFoto");
    imgPreview.src = urlPreview;
    imgPreview.classList.remove("d-none");
  } catch (err) {
    alert("❌ No se pudo optimizar la imagen");
  }
});

document.getElementById("btnQuitarFoto")?.addEventListener("click", () => {
  document.getElementById("inputFoto").value = "";
  const imgPreview = document.getElementById("previewFoto");
  imgPreview.src = "";
  imgPreview.classList.add("d-none");
  document.getElementById("btnQuitarFoto").classList.add("d-none");
  window.fotoOptimizada = null;
});

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
  if (!adminCard) return;
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
          stockFiltrado[talle] = 0;
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
            const nuevasFotos = window.fotosAdicionalesExistentes.filter((_, i) => i !== index);
            window.fotosAdicionalesExistentes = nuevasFotos;
            const productoActualizado = { ...producto, fotos_adicionales: nuevasFotos };
            cargarProductoEnFormulario(productoActualizado);
            console.log(`🗑️ Foto adicional ${index + 1} eliminada`);
          }
        };
        
        img.onclick = () => {
          if (typeof window.openModal === 'function') {
            window.openModal(url);
          } else {
            console.error("openModal no está definida");
          }
        };
        
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
  } else {
    if (titulo && titulo.id === "tituloFormularioAdmin") {
      titulo.textContent = "➕ Nuevo Producto";
      titulo.classList.remove("text-warning");
    }
    btnCancelar.style.display = "none";
    btnConfirmar.innerHTML = "✅ Confirmar";
    btnConfirmar.classList.remove("btn-warning");
    btnConfirmar.classList.add("btn-success");
  }
}

function resetearFormularioAdmin() {
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
  if (previewDiv) previewDiv.innerHTML = '';
  const fotosInput = document.getElementById("fotosAdicionales");
  if (fotosInput) fotosInput.value = "";
  window.fotosAdicionalesExistentes = null;
  const btnConfirmar = document.getElementById("btnConfirmarProd");
  if (btnConfirmar) {
    btnConfirmar.innerHTML = "✅ Confirmar";
    btnConfirmar.classList.remove("btn-warning");
    btnConfirmar.classList.add("btn-success");
  }
  const btnCancelar = document.getElementById("btnCancelarEdicion");
  if (btnCancelar) btnCancelar.style.display = "none";
  window.productoEditandoId = null;
  if (typeof toggleModoEdicion === "function") toggleModoEdicion(false);
}

document.getElementById("btnConfirmarProd")?.addEventListener("click", async () => {
  const email = window.cliente?.email;
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
        const precioNuevo = parseFloat(document.getElementById("precioProd").value);
        
        if (!isNaN(precioNuevo) && precioViejo > precioNuevo) {
          precioAnteriorParaEnviar = precioViejo;
        } else {
          precioAnteriorParaEnviar = 0;
        }
      }
    }

    let foto_url = "";
    if (window.fotoOptimizada) {
      const formData = new FormData();
      formData.append("file", window.fotoOptimizada, "producto.jpg");
      formData.append("email", email);

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
    } else if (window.productoEditandoId) {
      const productoExistente = window.todosLosProductos?.find(p => p.id_base === window.productoEditandoId);
      foto_url = productoExistente?.imagen_url || "";
    }
    const fotosAdicionalesUrls = [];
    
    if (window.fotosAdicionalesExistentes && window.fotosAdicionalesExistentes.length > 0) {
      fotosAdicionalesUrls.push(...window.fotosAdicionalesExistentes);
    }
    
    const fotosInput = document.getElementById('fotosAdicionales');
    if (fotosInput && fotosInput.files && fotosInput.files.length > 0) {
      
      for (let i = 0; i < fotosInput.files.length; i++) {
        try {
          const file = fotosInput.files[i];

          let blobOptimizado;
          try {
            blobOptimizado = await optimizarImagen(file);
          } catch (e) {
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
            continue; 
          }

          const data = await resp.json();
          if (data.url) {
            fotosAdicionalesUrls.push(data.url);
          }
        } catch (err) {
          continue;
        }
      }
    }

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

    if (window.productoEditandoId && precioViejo > precioNuevo) {
      try {
        const historial = JSON.parse(localStorage.getItem('historial_precios') || '{}');
        historial[window.productoEditandoId] = precioViejo;
        localStorage.setItem('historial_precios', JSON.stringify(historial));
      } catch(e) {
        // ignore
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
    } else {
      producto.precio_anterior = 0;
    }

    const endpoint = "https://mpagina.onrender.com/guardar-producto";
    
    const respGuardar = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!respGuardar.ok) {
      const text = await respGuardar.text();
      throw new Error(`Error al guardar producto: ${respGuardar.status} ${text}`);
    }

    const data = await respGuardar.json();

    if (data.status === "ok") {
      const mensaje = esEdicion ? 
        `✅ Producto actualizado correctamente (${fotosAdicionalesUrls.length} fotos adicionales)` : 
        `✅ Producto creado correctamente (${fotosAdicionalesUrls.length} fotos adicionales)`;
      
      const tieneOferta = data.resultado?.tiene_oferta || precioAnteriorParaEnviar > 0;
      const precioAnteriorBackend = data.resultado?.precio_anterior || precioAnteriorParaEnviar;
      
      if (tieneOferta && precioAnteriorBackend > 0) {
        const descuento = Math.round(((precioAnteriorBackend - precioNuevo) / precioAnteriorBackend) * 100);
        alert(`${mensaje}\n🔥 ¡OFERTA DETECTADA! -${descuento}% de descuento`);
      } else {
        alert(mensaje);
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
      alert("❌ " + (data.error || data.message || "Error al guardar producto"));
    }
  } catch (err) {
    alert("❌ Error al guardar producto: " + err.message);
  }
});

document.getElementById("tallesProd")?.addEventListener("input", function() {
  const talles = this.value.split(",").map(t => t.trim()).filter(Boolean);
  const container = document.getElementById("stockPorTalleContainer");
  const simpleContainer = document.getElementById("stockSimple");
  if (talles.length > 0) {
    container.style.display = "block";
    simpleContainer.style.display = "none";
    const stockPorTalleInput = document.getElementById("stockPorTalle");
    if (stockPorTalleInput) {
      const estaEditando = !!window.productoEditandoId;
      const stockEstaVacio = !stockPorTalleInput.value.trim();
      if ((!estaEditando && stockEstaVacio) || stockEstaVacio) {
        const nuevoStock = talles.map(t => `${t}:0`).join(", ");
        stockPorTalleInput.value = nuevoStock;
      } else if (!estaEditando && !stockEstaVacio) {
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
            if (stockExistente[talle] !== undefined) return `${talle}:${stockExistente[talle]}`;
            else return `${talle}:0`;
          }).join(", ");
          stockPorTalleInput.value = nuevoStock;
        } catch (error) {
          const nuevoStock = talles.map(t => `${t}:0`).join(", ");
          stockPorTalleInput.value = nuevoStock;
        }
      }
    }
  } else {
    container.style.display = "none";
    simpleContainer.style.display = "block";
  }
});

function salirAdmin() {
  console.log("🚪 Saliendo de modo admin, limpiando token...");
  window.modoAdmin = false;
  window.tokenAdmin = null;
  history.replaceState(null, "", window.location.pathname);
  const loginToggleBtn = document.getElementById("loginToggleBtn");
  if (loginToggleBtn) loginToggleBtn.style.display = "none";
  const logoutWrapper = document.getElementById("logoutAdminWrapper");
  if (logoutWrapper) logoutWrapper.style.display = "none";
  const adminCard = document.getElementById("adminCard");
  if (adminCard) adminCard.classList.add("d-none");
  const configurarMP = document.getElementById("configurarMP");
  if (configurarMP) configurarMP.classList.add("d-none");
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
  console.log("✅ Modo admin desactivado, vista restaurada.");
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

function toggleModoAdmin(activo) {
  document.querySelectorAll(".btnEliminarCard").forEach(btn => {
    if (activo) {
      btn.classList.remove("d-none");
    } else {
      btn.classList.add("d-none");
    }
  });
}
