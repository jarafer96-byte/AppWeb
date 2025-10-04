from flask import Flask, render_template, request, redirect, session, send_file
import os
from werkzeug.utils import secure_filename
from generator import generar_sitio
from generator import estilos

app = Flask(__name__)
app.secret_key = 'clave-secreta'
UPLOAD_FOLDER = 'static/img'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        session['tipo_web'] = request.form['tipo_web']
        return redirect('/estilo')
    return render_template('step1.html')

@app.route('/estilo', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        session['color'] = request.form.get('color')
        session['fuente'] = request.form.get('fuente')
        session['estilo'] = request.form.get('estilo')
        session['bordes'] = request.form.get('bordes')
        session['botones'] = request.form.get('botones')
        session['idioma'] = request.form.get('idioma')
        session['vista_imagenes'] = request.form.get('vista_imagenes')
        session['estilo_visual'] = request.form.get('estilo_visual')  # ✅ Nuevo campo

        logo = request.files.get('logo')
        if logo:
            filename = secure_filename(logo.filename)
            logo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            session['logo'] = filename
        else:
            session['logo'] = None

        return redirect('/contenido')
    return render_template('step2.html', estilos=estilos, config=session)

@app.route('/contenido', methods=['GET', 'POST'])
def step3():
    tipo = session.get('tipo_web')
    if request.method == 'POST':
        bloques = []

        if tipo in ['catálogo', 'menú']:
            nombres = request.form.getlist('nombre')
            descripciones = request.form.getlist('descripcion')
            precios = request.form.getlist('precio')
            imagenes = request.files.getlist('imagen')

            for i in range(len(nombres)):
                img = imagenes[i]
                filename = secure_filename(img.filename)
                img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bloques.append({
                    'nombre': nombres[i],
                    'descripcion': descripciones[i],
                    'precio': precios[i],
                    'imagen': filename
                })

        elif tipo == 'presentación':
            titulos = request.form.getlist('titulo')
            textos = request.form.getlist('texto')
            fotos = request.files.getlist('foto')

            for i in range(len(titulos)):
                img = fotos[i]
                filename = secure_filename(img.filename)
                img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bloques.append({
                    'titulo': titulos[i],
                    'texto': textos[i],
                    'foto': filename
                })

        elif tipo == 'evento':
            nombres = request.form.getlist('nombre_evento')
            descripciones = request.form.getlist('descripcion_evento')
            fechas = request.form.getlist('fecha')
            ubicaciones = request.form.getlist('ubicacion')
            imagenes = request.files.getlist('imagen_evento')

            for i in range(len(nombres)):
                img = imagenes[i]
                filename = secure_filename(img.filename)
                img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bloques.append({
                    'nombre_evento': nombres[i],
                    'descripcion_evento': descripciones[i],
                    'fecha': fechas[i],
                    'ubicacion': ubicaciones[i],
                    'imagen_evento': filename
                })

        session['bloques'] = bloques
        return redirect('/preview')

    return render_template('step3.html', tipo_web=tipo)

@app.route('/preview')
def preview():
    config = {
        'tipo_web': session.get('tipo_web'),
        'color': session.get('color'),
        'fuente': session.get('fuente'),
        'estilo': session.get('estilo'),
        'bordes': session.get('bordes'),
        'botones': session.get('botones'),
        'idioma': session.get('idioma'),
        'vista_imagenes': session.get('vista_imagenes'),
        'logo': session.get('logo'),
        'estilo_visual': session.get('estilo_visual'),  # ✅ Nuevo campo
        'titulo': 'Mi sitio personalizado',
        'descripcion': 'Este sitio fue generado automáticamente.',
        'productos': session.get('bloques') if session.get('tipo_web') in ['catálogo', 'menú'] else [],
        'bloques': session.get('bloques') if session.get('tipo_web') not in ['catálogo', 'menú'] else []
    }

    textos = {
        'es': {'contacto': 'Contactar por WhatsApp', 'precio': 'Precio'},
        'en': {'contacto': 'Contact via WhatsApp', 'precio': 'Price'},
        'pt': {'contacto': 'Contato via WhatsApp', 'precio': 'Preço'}
    }

    return render_template('preview.html', config=config, textos=textos)

@app.route('/descargar')
def descargar():
    archivo = generar_sitio(session)
    return send_file(archivo, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
