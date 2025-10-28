from flask import Flask, render_template, request, redirect, session, url_for
from db_conn import create_connection
import os

frontend_path = os.path.join(os.path.dirname(__file__), '../frontend')

app = Flask(__name__, template_folder=frontend_path)
app.secret_key = "secret123"

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM akun 
            WHERE Username=%s AND Password=%s
        """, (username, password))
        akun = cursor.fetchone()

        if akun:
            session['username'] = akun['Username']

            # Cek role-nya
            if akun['nim_mahasiswa']:
                session['role'] = 'mahasiswa'
                return redirect(url_for('dashboard_mahasiswa'))
            elif akun['nip_dosen']:
                session['role'] = 'dosen'
                return redirect(url_for('dashboard_dosen'))
            elif akun['nip_kaprodi']:
                session['role'] = 'kaprodi'
                return redirect(url_for('dashboard_kaprodi'))
            elif akun['id_admin']:
                session['role'] = 'admin'
                return redirect(url_for('dashboard_admin'))
        else:
            return render_template('login_page.html', error="Username atau password salah!")

    return render_template('login_page.html')

@app.route('/dashboard/mahasiswa')
def dashboard_mahasiswa():
    if session.get('role') == 'mahasiswa':
        return render_template('dashboard_mhs.html', user=session['username'])
    return redirect(url_for('login'))

@app.route('/dashboard/dosen')
def dashboard_dosen():
    if session.get('role') == 'dosen':
        return render_template('dashboard_dosen.html', user=session['username'])
    return redirect(url_for('login'))

@app.route('/dashboard/kaprodi')
def dashboard_kaprodi():
    if session.get('role') == 'kaprodi':
        return render_template('dashboard_kaprodi.html', user=session['username'])
    return redirect(url_for('login'))

@app.route('/dashboard/admin')
def dashboard_admin():
    if session.get('role') == 'admin':
        return render_template('dashboard_admin.html', user=session['username'])
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)