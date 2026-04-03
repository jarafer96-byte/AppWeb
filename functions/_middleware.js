export async function onRequest(context) {
  const url = new URL(context.request.url);
  const path = url.pathname;

  // Lista de rutas que deben ir al backend de Render
  const backendRoutes = [
    '/api/',               // todas las rutas /api/*
    '/pagar',
    '/verificar-stock',
    '/login-admin',
    '/guardar-producto',
    '/eliminar-producto',
    '/subir-foto',
    '/conectar_mp',
    '/actualizar-stock-talle',
    '/guardar-talles-stock',
    '/callback_mp'
  ];

  // Verificar si la ruta actual debe ir al backend
  const shouldGoToBackend = backendRoutes.some(route => 
    route === path || (route.endsWith('/') && path.startsWith(route))
  );

  if (shouldGoToBackend) {
    const backendUrl = `https://mpagina.onrender.com${path}${url.search}`;
    return fetch(backendUrl, context.request);
  }

  // Para el resto, continuar con el contenido estático
  return context.next();
}
