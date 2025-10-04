import os
from zipfile import ZipFile
from jinja2 import Environment, FileSystemLoader

# Diccionario de estilos visuales
estilos = {
    "oscuro_neon": {
        "fondo": "#000000",
        "fuente": "Orbitron",
        "color_primario": "#00f0ff",
        "boton_whatsapp": "glow",
        "cards": "borde-neon"
    },
    "claro_moderno": {
        "fondo": "#ffffff",
        "fuente": "Poppins",
        "color_primario": "#007bff",
        "boton_whatsapp": "sombra",
        "cards": "sombra-suave"
    },
    "elegante_gradiente": {
        "fondo": "linear-gradient(to bottom right, #e0f7fa, #fce4ec)",
        "fuente": "Playfair Display",
        "color_primario": "#6a1b9a",
        "boton_whatsapp": "borde-dorado",
        "cards": "borde-elegante"
    },
    "vibrante_fiesta": {
        "fondo": "linear-gradient(to bottom right, #ff4081, #ffff00)",
        "fuente": "Fredoka",
        "color_primario": "#ff4081",
        "boton_whatsapp": "bounce",
        "cards": "sombra-colores"
    },
    "creativo_divertido": {
        "fondo": "#fef3bd",
        "fuente": "Comic Neue",
        "color_primario": "#ff9800",
        "boton_whatsapp": "animado",
        "cards": "curvas-divertidas"
    },
    "minimalista_blanco": {
        "fondo": "#f9f9f9",
        "fuente": "Inter",
        "color_primario": "#333333",
        "boton_whatsapp": "simple",
        "cards": "sin-borde"
    }
    # 🔜 Podés agregar los otros 54 estilos acá
}

def generar_sitio(session):
    estilo = estilos.get(session.get('estilo_visual'), estilos['claro_moderno'])

    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('base.html')

    html = template.render(
        config=session,
        estilo=estilo,
        productos=session.get('bloques', [])
    )

    os.makedirs('sitio_generado', exist_ok=True)
    with open('sitio_generado/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    zip_path = 'sitio.zip'
    with ZipFile(zip_path, 'w') as zipf:
        zipf.write('sitio_generado/index.html', arcname='index.html')

    return zip_path
