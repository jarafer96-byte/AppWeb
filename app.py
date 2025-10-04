from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import shutil
from generator import generar_sitio

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

# Ruta inicial
@app.route('/')
def home():
    return redirect(url_for('step1'))

# Paso 1: Tipo de sitio
@app.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        tipo_web = request.form.get('tipo_web')
        session['tipo_web'] = tipo_web
        return redirect(url_for('step2'))
    return render_template('step1.html')

# Paso 2: Diseño visual
@app.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        color = request.form.get('color')
        fuente = request.form.get('fuente')
        botones = request.form.get('botones')
        session['color'] = color
        session['fuente'] = fuente
        session['botones'] = botones
        return redirect(url_for('step3'))
    return render_template('step2.html')

# Paso 3: Contenido
@app.route('/step3', methods=['GET', 'POST'])
def step3():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        imagen = request.files.get('imagen')

        session['titulo'] = titulo
        session['descripcion'] = descripcion

        if imagen and imagen.filename != '':
            ruta_img = os.path.join('static', 'img', imagen.filename)
            imagen.save(ruta_img)
            session['imagen'] = imagen.filename
        else:
            session['imagen'] = 'default.jpg'

        return redirect(url_for('step4'))
    return render_template('step3.html')

# Paso 4: Funciones extra
@app.route('/step4', methods=['GET', 'POST'])
def step4():
    if request.method == 'POST':
        contacto = request.form.get('contacto')
        whatsapp = request.form.get('whatsapp')
        pago = request.form.get('pago')

        session['contacto'] = contacto
        session['whatsapp'] = whatsapp
        session['pago'] = pago

        return redirect(url_for('preview'))
    return render_template('step4.html')

# Vista previa
@app.route('/preview')
def preview():
    config = {
        'tipo_web': session.get('tipo_web', 'catálogo'),
        'color': session.get('color', '#0077cc'),
        'fuente': session.get('fuente', 'Arial'),
        'botones': session.get('botones', 'redondeado'),
        'titulo': session.get('titulo', 'Mi sitio'),
        'descripcion': session.get('descripcion', ''),
        'imagen': session.get('imagen', 'default.jpg'),
        'contacto': session.get('contacto', 'no'),
        'whatsapp': session.get('whatsapp', 'no'),
        'pago': session.get('pago', 'ninguno')
    }
    return render_template('preview.html', config=config)

# Paso 5: Generación y descarga
@app.route('/step5', methods=['GET', 'POST'])
def step5():
    if request.method == 'POST':
        config = {
            'tipo_web': session.get('tipo_web', 'catálogo'),
            'color': session.get('color', '#0077cc'),
            'fuente': session.get('fuente', 'Arial'),
            'botones': session.get('botones', 'redondeado'),
            'titulo': session.get('titulo', 'Mi sitio'),
            'descripcion': session.get('descripcion', ''),
            'imagen': session.get('imagen', 'default.jpg'),
            'contacto': session.get('contacto', 'no'),
            'whatsapp': session.get('whatsapp', 'no'),
            'pago': session.get('pago', 'ninguno')
        }

        zip_path = generar_sitio(config)
        return send_file(zip_path, as_attachment=True)

    return render_template('step5.html')

# Ejecutar la app
if __name__ == '__main__':
    app.run(debug=True)
