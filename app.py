from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import shutil
from generator import generar_sitio

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

@app.route('/')
def home():
    return redirect(url_for('step1'))

@app.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        session['tipo_web'] = request.form.get('tipo_web')
        return redirect(url_for('step2'))
    return render_template('step1.html')

@app.route('/step2', methods=['GET', 'POST'])
def step2():
    if request.method == 'POST':
        session['color'] = request.form.get('color')
        session['fuente'] = request.form.get('fuente')
        session['botones'] = request.form.get('botones')
        return redirect(url_for('step3'))
    return render_template('step2.html')

@app.route('/step3', methods=['GET', 'POST'])
def step3():
    if request.method == 'POST':
        os.makedirs('static/img', exist_ok=True)
        tipo = session.get('tipo_web', 'catálogo')

        if tipo == 'catálogo':
            productos = []
            for i in range(1, 6):
                nombre = request.form.get(f'nombre_{i}')
                descripcion = request.form.get(f'desc_{i}')
                precio = request.form.get(f'precio_{i}')
                imagen = request.files.get(f'img_{i}')

                if nombre and descripcion:
                    filename = 'default.jpg'
                    if imagen and imagen.filename != '':
                        filename = imagen.filename
                        imagen.save(os.path.join('static', 'img', filename))

                    productos.append({
                        'nombre': nombre,
                        'descripcion': descripcion,
                        'precio': precio,
                        'imagen': filename
                    })
            session['productos'] = productos
        else:
            session['titulo'] = request.form.get('titulo')
            session['descripcion'] = request.form.get('descripcion')
            imagen = request.files.get('imagen')
            if imagen and imagen.filename != '':
                imagen.save(os.path.join('static', 'img', imagen.filename))
                session['imagen'] = imagen.filename
            else:
                session['imagen'] = 'default.jpg'

        return redirect(url_for('step4'))
    return render_template('step3.html')

@app.route('/step4', methods=['GET', 'POST'])
def step4():
    if request.method == 'POST':
        session['contacto'] = request.form.get('contacto')
        session['whatsapp'] = request.form.get('whatsapp')
        session['pago'] = request.form.get('pago')
        return redirect(url_for('preview'))
    return render_template('step4.html')

@app.route('/preview')
def preview():
    config = {
        'tipo_web': session.get('tipo_web'),
        'color': session.get('color'),
        'fuente': session.get('fuente'),
        'botones': session.get('botones'),
        'titulo': session.get('titulo'),
        'descripcion': session.get('descripcion'),
        'imagen': session.get('imagen'),
        'contacto': session.get('contacto'),
        'whatsapp': session.get('whatsapp'),
        'pago': session.get('pago'),
        'productos': session.get('productos', [])
    }
    return render_template('preview.html', config=config)

@app.route('/step5', methods=['GET', 'POST'])
def step5():
    if request.method == 'POST':
        config = {
            'tipo_web': session.get('tipo_web'),
            'color': session.get('color'),
            'fuente': session.get('fuente'),
            'botones': session.get('botones'),
            'titulo': session.get('titulo'),
            'descripcion': session.get('descripcion'),
            'imagen': session.get('imagen'),
            'contacto': session.get('contacto'),
            'whatsapp': session.get('whatsapp'),
            'pago': session.get('pago'),
            'productos': session.get('productos', [])
        }
        zip_path = generar_sitio(config)
        return send_file(zip_path, as_attachment=True)
    return render_template('step5.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
