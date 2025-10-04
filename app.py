from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesiones'

@app.route('/')
def home():
    return redirect(url_for('step1'))

@app.route('/step1', methods=['GET', 'POST'])
def step1():
    if request.method == 'POST':
        tipo_web = request.form.get('tipo_web')
        session['tipo_web'] = tipo_web
        return redirect(url_for('step2'))
    return render_template('step1.html')

@app.route('/step2')
def step2():
    tipo = session.get('tipo_web', 'No definido')
    return f"Elegiste: {tipo}. Acá iría el paso 2."

if __name__ == '__main__':
    app.run(debug=True)
