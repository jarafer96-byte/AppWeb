import os
from zipfile import ZipFile
from jinja2 import Environment, FileSystemLoader

# Diccionario de estilos visuales
estilos = {
    # CLAROS
    "claro_moderno": {"fondo": "#ffffff", "fuente": "Poppins", "color_primario": "#007bff", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "claro_pastel": {"fondo": "#fefefe", "fuente": "Quicksand", "color_primario": "#ffb6c1", "boton_whatsapp": "simple", "cards": "sombra-suave"},
    "claro_blanco_azul": {"fondo": "#f0f8ff", "fuente": "Nunito", "color_primario": "#1e90ff", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "claro_crema": {"fondo": "#fffaf0", "fuente": "Lato", "color_primario": "#ff8c00", "boton_whatsapp": "simple", "cards": "sombra-suave"},
    "claro_lila": {"fondo": "#f3e5f5", "fuente": "Raleway", "color_primario": "#ba68c8", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "claro_verde_menta": {"fondo": "#e0f2f1", "fuente": "Montserrat", "color_primario": "#26a69a", "boton_whatsapp": "simple", "cards": "sombra-suave"},
    "claro_naranja": {"fondo": "#fff3e0", "fuente": "Open Sans", "color_primario": "#ff9800", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "claro_celeste": {"fondo": "#e3f2fd", "fuente": "Ubuntu", "color_primario": "#2196f3", "boton_whatsapp": "simple", "cards": "sombra-suave"},
    "claro_rosado": {"fondo": "#fce4ec", "fuente": "Comfortaa", "color_primario": "#ec407a", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "claro_gris_suave": {"fondo": "#f5f5f5", "fuente": "Inter", "color_primario": "#616161", "boton_whatsapp": "simple", "cards": "sombra-suave"},

    # OSCUROS
    "oscuro_neon": {"fondo": "#000000", "fuente": "Orbitron", "color_primario": "#00f0ff", "boton_whatsapp": "glow", "cards": "borde-neon"},
    "oscuro_minimal": {"fondo": "#121212", "fuente": "Inter", "color_primario": "#ffffff", "boton_whatsapp": "simple", "cards": "sin-borde"},
    "oscuro_dorado": {"fondo": "#1c1c1c", "fuente": "Playfair Display", "color_primario": "#ffd700", "boton_whatsapp": "borde-dorado", "cards": "borde-elegante"},
    "oscuro_purpura": {"fondo": "#2c003e", "fuente": "Rubik", "color_primario": "#9c27b0", "boton_whatsapp": "glow", "cards": "borde-neon"},
    "oscuro_azul_noche": {"fondo": "#0d1b2a", "fuente": "Roboto", "color_primario": "#1e88e5", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "oscuro_verde_glow": {"fondo": "#002b1f", "fuente": "Fira Sans", "color_primario": "#00e676", "boton_whatsapp": "glow", "cards": "borde-neon"},
    "oscuro_negro_total": {"fondo": "#000000", "fuente": "IBM Plex Sans", "color_primario": "#ffffff", "boton_whatsapp": "simple", "cards": "sin-borde"},
    "oscuro_grafito": {"fondo": "#1a1a1a", "fuente": "Work Sans", "color_primario": "#9e9e9e", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "oscuro_aurora": {"fondo": "linear-gradient(to bottom, #0f2027, #203a43, #2c5364)", "fuente": "Exo", "color_primario": "#00bcd4", "boton_whatsapp": "glow", "cards": "borde-neon"},
    "oscuro_luz_sutil": {"fondo": "#1e1e1e", "fuente": "Source Sans Pro", "color_primario": "#cfd8dc", "boton_whatsapp": "sombra", "cards": "sombra-suave"},

    # ELEGANTES
    "elegante_gradiente": {"fondo": "linear-gradient(to bottom right, #e0f7fa, #fce4ec)", "fuente": "Playfair Display", "color_primario": "#6a1b9a", "boton_whatsapp": "borde-dorado", "cards": "borde-elegante"},
    "elegante_serif": {"fondo": "#fdf6e3", "fuente": "Merriweather", "color_primario": "#795548", "boton_whatsapp": "simple", "cards": "borde-elegante"},
    "elegante_dorado": {"fondo": "#fff8e1", "fuente": "Cormorant Garamond", "color_primario": "#d4af37", "boton_whatsapp": "borde-dorado", "cards": "borde-elegante"},
    "elegante_plateado": {"fondo": "#eceff1", "fuente": "Lora", "color_primario": "#90a4ae", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "elegante_azul_marino": {"fondo": "#001f3f", "fuente": "Libre Baskerville", "color_primario": "#0074D9", "boton_whatsapp": "sombra", "cards": "borde-elegante"},
    "elegante_lavanda": {"fondo": "#e6e6fa", "fuente": "Crimson Text", "color_primario": "#9370db", "boton_whatsapp": "simple", "cards": "sombra-suave"},
    "elegante_crema": {"fondo": "#fffdd0", "fuente": "Georgia", "color_primario": "#8b4513", "boton_whatsapp": "simple", "cards": "borde-elegante"},
    "elegante_negro_oro": {"fondo": "#212121", "fuente": "Tinos", "color_primario": "#ffcc00", "boton_whatsapp": "borde-dorado", "cards": "borde-elegante"},
    "elegante_rosa_palo": {"fondo": "#f8bbd0", "fuente": "Vollkorn", "color_primario": "#ad1457", "boton_whatsapp": "sombra", "cards": "sombra-suave"},
    "elegante_azul_real": {"fondo": "#e3f2fd", "fuente": "PT Serif", "color_primario": "#0d47a1", "boton_whatsapp": "sombra", "cards": "borde-elegante"},

    # VIBRANTES
    "vibrante_fiesta": {"fondo": "linear-gradient(to bottom right, #ff4081, #ffff00)", "fuente": "Fredoka", "color_primario": "#ff4081", "boton_whatsapp": "bounce", "cards": "sombra-colores"},
    "vibrante_arcoiris": {"fondo": "linear-gradient(to right, red, orange, yellow, green, blue, indigo, violet)", "fuente": "Baloo 2", "color_primario": "#ff00cc", "boton_whatsapp": "animado", "cards": "curvas-divertidas"},
    "vibrante_magenta": {"fondo": "#f50057", "fuente": "Bangers", "color_primario": "#ffffff", "boton_whatsapp": "glow", "cards": "sombra-colores"},
    "vibrante_naranja_amarillo": {"fondo": "linear-gradient(to bottom right, #ff9800, #ffff00)", "fuente": "Chewy", "color_primario": "#ff9800", "boton_whatsapp": "bounce", "cards": "curvas-divertidas"},
    "vibrante_turquesa": {"fondo": "#00bcd4", "fuente": "Kanit", "color_primario": "#ffffff", "boton_whatsapp": "sombra", "cards": "sombra-colores"},
    "vibrante_rosa_fluor": {"fondo": "#ff1493", "fuente": "Lilita One", "color_primario": "#ffffff", "boton_whatsapp": "animado", "cards": "sombra-colores"},
    "vibrante_verde_lima": {"fondo": "#cddc39", "fuente": "Concert One", "color_primario": "#33691e", "boton_whatsapp": "bounce", "cards": "curvas-divertidas"},
    "vibrante_multicolor": {"fondo": "linear-gradient(45deg, #ff5722, #ffeb3b, #4caf50, #2196f3)", "fuente": "Titan One", "color_primario": "#ffffff", "boton_whatsapp": "animado", "cards": "sombra-colores"},
    "vibrante_rojo_azul": {"fondo": "linear-gradient(to right, #f44336, #2196f3)", "fuente": "Luckiest Guy", "color_primario": "#ffffff", "boton_whatsapp": "glow", "cards": "curvas-divertidas"},
    "vibrante_amarillo_purpura": {"fondo": "linear-gradient(to bottom right, #ffeb3b, #9c27b0)", "fuente": "Shrikhand", "color_primario": "#ffffff", "boton_whatsapp": "bounce", "cards": "sombra-colores"},

    # CREATIVOS
    "creativo_divertido": {"fondo": "#fef3bd", "fuente": "Comic Neue", "color_primario": "#ff9800", "boton_whatsapp": "animado", "cards": "curvas-divertidas"},
    "creativo_comic": {"fondo": "#fff8dc", "fuente": "Bangers", "color_primario": "#ff5722", "boton_whatsapp": "bounce", "cards": "curvas-divertidas"},
    "creativo_chalkboard": {"fondo": "#2e2e2e", "fuente": "Gloria Hallelujah", "color_primario": "#ffffff", "boton_whatsapp": "simple", "cards": "sin-borde"},
    "creativo_ondas": {"fondo": "linear-gradient(to right, #00c9ff, #92fe9d)", "fuente": "Indie Flower", "color_primario": "#00c9ff", "boton_whatsapp": "animado", "cards": "curvas-divertidas"},
    "creativo_pinceladas": {"fondo": "#fff0f5", "fuente": "Caveat", "color_primario": "#ff69b4", "boton_whatsapp": "sombra", "cards": "sombra-colores"},
    "creativo_doodle": {"fondo": "#f0fff0", "fuente": "Patrick Hand", "color_primario": "#4caf50", "boton_whatsapp": "bounce", "cards": "curvas-divertidas"},
    "creativo_animado": {"fondo": "#ffe4e1", "fuente": "Permanent Marker", "color_primario": "#ff4081", "boton_whatsapp": "animado", "cards": "sombra-colores"},
    "creativo_abstracto": {"fondo": "linear-gradient(to bottom right, #ffccbc, #d1c4e9)", "fuente": "Architects Daughter", "color_primario": "#7e57c2", "boton_whatsapp": "sombra", "cards": "curvas-divertidas"},
    "creativo_infancia": {"fondo": "#fff9c4", "fuente": "Schoolbell", "color_primario": "#fbc02d", "boton_whatsapp": "bounce", "cards": "curvas-divertidas"},
    "creativo_explosivo": {"fondo": "linear-gradient(to right, #ff6f00, #ffeb3b)", "fuente": "Rock Salt", "color_primario": "#ff6f00", "boton_whatsapp": "glow", "cards": "sombra-colores"},
