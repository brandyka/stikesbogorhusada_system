from flask import Flask, render_template, request, redirect, session, url_for,send_from_directory
from db_conn import create_connection
import os

frontend_path = os.path.join(os.path.dirname(__file__), '../frontend')

app = Flask(__name__, template_folder=frontend_path)
app.secret_key = "secret123"

@app.route('/gambar/<path:filename>')
def gambar(filename):
    return send_from_directory('gambar', filename)

@app.route('/')
def home():
    return redirect(url_for('login'))

#================================= LOGIN =====================================================
#=============================================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM akun WHERE Username=%s AND Password=%s
        """, (username, password))
        akun = cursor.fetchone()

        if akun:
            session['username'] = akun['Username']

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

#============================== MAHASISWA SECTION ===============================
#================================================================================
@app.route('/dashboard/mahasiswa')
def dashboard_mahasiswa():
    if session.get('role') != 'mahasiswa':
        return redirect(url_for('login'))
        
    try:
        username = session.get('username')
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        sql_query = """
            SELECT 
                m.NIM, 
                m.Nama, 
                k.nama_kelas, 
                a.tahun AS angkatan_tahun
            FROM akun act
            JOIN mahasiswa m ON act.nim_mahasiswa = m.NIM
            LEFT JOIN kelas k ON m.id_kelas = k.id_kelas
            LEFT JOIN angkatan a ON m.id_angkatan = a.id_angkatan
            WHERE act.Username = %s
        """
        cursor.execute(sql_query, (username,))
        mahasiswa_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if not mahasiswa_data:
            session.clear()
            return redirect(url_for('login', error="Data profil tidak ditemukan."))
        return render_template('dashboard_mhs.html', 
                               user=username, 
                               data=mahasiswa_data) 
    except Exception as e:
        print(f"Error fetching mahasiswa dashboard data: {e}")
        return "Terjadi error saat mengambil data profil."

#=============================== DOSEN SECTION ===================================
#=================================================================================
@app.route('/dashboard/dosen')
def dashboard_dosen():
    if session.get('role') == 'dosen':
        return render_template('dashboard_dosen.html', user=session['username'])
    return redirect(url_for('login'))

#================================= KAPRODI SECTION ================================
#==================================================================================
@app.route('/dashboard/kaprodi')
def dashboard_kaprodi():
    if session.get('role') == 'kaprodi':
        return render_template('dashboard_kaprodi.html', user=session['username'])
    return redirect(url_for('login'))


#================================== ADMIN SECTION ==================================
#===================================================================================
@app.route('/dashboard/admin')
def dashboard_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 1. Siapkan dictionary untuk menampung data hitungan
    counts = {
        'mahasiswa': 0,
        'dosen': 0,
        'matakuliah': 0,
        'permintaan': 0
    }
    
    conn = None
    cursor = None
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 

        # 2. Query untuk menghitung mahasiswa
        cursor.execute("SELECT COUNT(*) AS total FROM mahasiswa")
        count_mhs = cursor.fetchone()
        if count_mhs:
            counts['mahasiswa'] = count_mhs['total']

        # 3. Query untuk menghitung dosen
        cursor.execute("SELECT COUNT(*) AS total FROM dosen")
        count_dosen = cursor.fetchone()
        if count_dosen:
            counts['dosen'] = count_dosen['total']

        # 4. Query untuk menghitung mata kuliah (menggunakan 'matkul' dari kode Anda)
        cursor.execute("SELECT COUNT(*) AS total FROM matkul")
        count_mk = cursor.fetchone()
        if count_mk:
            counts['matakuliah'] = count_mk['total']
        
        # 5. (Opsional) Query untuk permintaan jadwal
        # (Abaikan jika tabel 'permintaan_jadwal' belum ada)
        try:
            # Asumsi: Anda punya tabel 'permintaan_jadwal' dan status 'Pending'
            cursor.execute("SELECT COUNT(*) AS total FROM permintaan_jadwal WHERE status = 'Pending'")
            count_permintaan = cursor.fetchone()
            if count_permintaan:
                counts['permintaan'] = count_permintaan['total']
        except Exception as e_permintaan:
            print(f"Tidak dapat menghitung permintaan_jadwal (tabel mungkin belum ada): {e_permintaan}")
    
    except Exception as e:
        print(f"Error fetching dashboard counts: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # 6. Kirim 'counts' ke file HTML
    return render_template('admin/dashboard_admin.html', 
                           user=session['username'], 
                           counts=counts)
#================================= PAGE KELOLA DATA =================================
@app.route('/dashboard/admin/kelola-data')
def admin_kelola_data():
    if session.get('role') == 'admin':
        return render_template('admin/kelola_data_akademik.html', user=session['username'])
    return redirect(url_for('login'))

# KELOLA DATA DOSEN
@app.route('/dashboard/admin/kelola-data/dosen') 
def admin_kelola_dosen():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM dosen")
            
            daftar_dosen = cursor.fetchall()
            
            cursor.close()
            conn.close()
            return render_template('admin/kelola_dosen_list.html', user=session['username'], daftar_dosen=daftar_dosen)
        
        except Exception as e:
            print(f"Error reading database: {e}")
            return "Terjadi error saat mengambil data."    
    return redirect(url_for('login'))
@app.route('/dashboard/admin/kelola-data/dosen/hapus/<string:nip>') 
def hapus_dosen(nip):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dosen WHERE NIP = %s", (nip,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_kelola_dosen'))
@app.route('/dashboard/admin/kelola-data/dosen/tambah', methods=['GET', 'POST'])
def tambah_dosen():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        nip_baru = request.form['nip']
        nama_baru = request.form['nama']
        prodi_baru = request.form['program_studi']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO dosen (NIP, Nama, ProgramStudi) VALUES (%s, %s, %s)", 
                           (nip_baru, nama_baru, prodi_baru))
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_kelola_dosen'))
    return render_template('admin/tambah_dosen_form.html', user=session['username'])
@app.route('/dashboard/admin/kelola-data/dosen/edit/<string:nip>', methods=['GET', 'POST'])
def edit_dosen(nip):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        nama_baru = request.form['nama']
        prodi_baru = request.form['program_studi']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE dosen SET Nama = %s, ProgramStudi = %s WHERE NIP = %s",
                           (nama_baru, prodi_baru, nip))
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_kelola_dosen'))
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 
        
        cursor.execute("SELECT * FROM dosen WHERE NIP = %s", (nip,))
        dosen_data = cursor.fetchone() 
        if not dosen_data:
            return "Data Dosen tidak ditemukan.", 404
        return render_template('admin/edit_dosen_form.html', 
                               user=session['username'], 
                               dosen=dosen_data) 
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        cursor.close()
        conn.close()

# KELOLA DATA MAHASISWA
@app.route('/dashboard/admin/kelola-data/mahasiswa')
def admin_kelola_mahasiswa():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM mahasiswa") 
            
            daftar_mahasiswa = cursor.fetchall()
            
            cursor.close()
            conn.close()
            return render_template('admin/kelola_mahasiswa_list.html', 
                                    user=session['username'], 
                                    daftar_mahasiswa=daftar_mahasiswa) 
        
        except Exception as e:
            print(f"Error reading mahasiswa database: {e}")
            return "Terjadi error saat mengambil data."    
    return redirect(url_for('login'))

@app.route('/dashboard/admin/kelola-data/mahasiswa/hapus/<string:nim>')
def hapus_mahasiswa(nim):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mahasiswa WHERE NIM = %s", (nim,)) 
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_kelola_mahasiswa')) 

@app.route('/dashboard/admin/kelola-data/mahasiswa/tambah', methods=['GET', 'POST'])
def tambah_mahasiswa():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nim_baru = request.form['nim']
        nama_baru = request.form['nama']
        id_kelas_baru = request.form['id_kelas']
        id_angkatan_baru = request.form['id_angkatan']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO mahasiswa (NIM, Nama, id_kelas, id_angkatan) VALUES (%s, %s, %s, %s)", 
                           (nim_baru, nama_baru, id_kelas_baru, id_angkatan_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_mahasiswa')) 
    return render_template('admin/tambah_mahasiswa_form.html', user=session['username'])

@app.route('/dashboard/admin/kelola-data/mahasiswa/edit/<string:nim>', methods=['GET', 'POST'])
def edit_mahasiswa(nim):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama_baru = request.form['nama']
        id_kelas_baru = request.form['id_kelas']
        id_angkatan_baru = request.form['id_angkatan']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE mahasiswa SET Nama = %s, id_kelas = %s, id_angkatan = %s WHERE NIM = %s",
                           (nama_baru, id_kelas_baru, id_angkatan_baru, nim))
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_mahasiswa'))
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 
        
        cursor.execute("SELECT * FROM mahasiswa WHERE NIM = %s", (nim,))
        mahasiswa_data = cursor.fetchone() 
        
        if not mahasiswa_data:
            return "Data Mahasiswa tidak ditemukan.", 404
            
        return render_template('admin/edit_mahasiswa_form.html', 
                               user=session['username'], 
                               mahasiswa=mahasiswa_data) 
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        cursor.close()
        conn.close()

# KELOLA MATAKULIAH
@app.route('/dashboard/admin/kelola-data/matakuliah')
def admin_kelola_matakuliah():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            # Ganti 'SELECT * FROM mahasiswa' menjadi 'SELECT * FROM matakuliah'
            cursor.execute("SELECT * FROM matkul") 
            
            daftar_matakuliah = cursor.fetchall()
            
            cursor.close()
            conn.close()
            # Kirim ke file HTML yang baru
            return render_template('admin/kelola_matakuliah_list.html', 
                                    user=session['username'], 
                                    daftar_matakuliah=daftar_matakuliah) 
        
        except Exception as e:
            print(f"Error reading matakuliah database: {e}")
            return "Terjadi error saat mengambil data."    
    return redirect(url_for('login'))

@app.route('/dashboard/admin/kelola-data/matakuliah/hapus/<string:kodemk>')
def hapus_matakuliah(kodemk): # Ganti 'nim' menjadi 'kodemk'
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        # Ganti tabel, kolom, dan variabel
        cursor.execute("DELETE FROM matkul WHERE kd_mk = %s", (kodemk,)) 
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    # Redirect ke 'admin_kelola_matakuliah'
    return redirect(url_for('admin_kelola_matakuliah')) 

@app.route('/dashboard/admin/kelola-data/matakuliah/tambah', methods=['GET', 'POST'])
def tambah_matakuliah():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Sesuaikan dengan kolom DB Anda
        kodemk_baru = request.form['kd_mk']
        nama_matkul_baru = request.form['nama_matkul']
        sks_baru = request.form['sks']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            # Sesuaikan Query INSERT
            cursor.execute("INSERT INTO matkul (kd_mk, nama_matkul, sks) VALUES (%s, %s, %s)", 
                           (kodemk_baru, nama_matkul_baru, sks_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_matakuliah')) 

    # Tampilkan form tambah matakuliah
    return render_template('admin/tambah_matakuliah_form.html', user=session['username'])

@app.route('/dashboard/admin/kelola-data/matakuliah/edit/<string:kodemk>', methods=['GET', 'POST'])
def edit_matakuliah(kodemk): # Ganti 'nim' menjadi 'kodemk'
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Sesuaikan dengan kolom DB Anda (kd_mk adalah ID, tidak diubah)
        nama_matkul_baru = request.form['nama_matkul']
        sks_baru = request.form['sks']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            # Sesuaikan Query UPDATE
            cursor.execute("UPDATE matkul SET nama_matkul = %s, sks = %s WHERE kd_mk = %s",
                           (nama_matkul_baru, sks_baru, kodemk))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
            
            return redirect(url_for('admin_kelola_matakuliah'))

    # (Method GET)
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 
        
        # Sesuaikan Query SELECT
        cursor.execute("SELECT * FROM matkul WHERE kd_mk = %s", (kodemk,))
        matakuliah_data = cursor.fetchone() 
        
        if not matakuliah_data:
            return "Data Mata Kuliah tidak ditemukan.", 404
            
        # Kirim ke file HTML dan variabel yang baru
        return render_template('admin/edit_matakuliah_form.html', 
                               user=session['username'], 
                               matakuliah=matakuliah_data) 
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        cursor.close()
        conn.close()

#Kelola Kelas
@app.route('/dashboard/admin/kelola-data/kelas')
def admin_kelola_kelas():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            # Ganti 'SELECT * FROM mahasiswa' menjadi 'SELECT * FROM matakuliah'
            cursor.execute("SELECT * FROM kelas") 
            
            daftar_kelas = cursor.fetchall()
            
            cursor.close()
            conn.close()
            # Kirim ke file HTML yang baru
            return render_template('admin/kelola_kelas_list.html', 
                                    user=session['username'], 
                                    daftar_kelas=daftar_kelas) 
        
        except Exception as e:
            print(f"Error reading matakuliah database: {e}")
            return "Terjadi error saat mengambil data."    
    return redirect(url_for('login'))
@app.route('/dashboard/admin/kelola-data/kelas/hapus/<int:id_kelas>')
def hapus_kelas(id_kelas): # Ganti 'nim' menjadi 'kodemk'
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        # Ganti tabel, kolom, dan variabel
        cursor.execute("DELETE FROM kelas WHERE id_kelas = %s", (id_kelas,)) 
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    # Redirect ke 'admin_kelola_matakuliah'
    return redirect(url_for('admin_kelola_kelas')) 

@app.route('/dashboard/admin/kelola-data/kelas/tambah', methods=['GET', 'POST'])
def tambah_kelas():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Sesuaikan dengan kolom DB Anda
        id_kelas_baru = request.form['id_kelas']
        nama_kelas_baru = request.form['nama_kelas']

        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            # Sesuaikan Query INSERT
            cursor.execute("INSERT INTO kelas (id_kelas, nama_kelas) VALUES (%s, %s)", 
                           (id_kelas_baru, nama_kelas_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_kelas')) 

    # Tampilkan form tambah matakuliah
    return render_template('admin/tambah_kelas_form.html', user=session['username'])

@app.route('/dashboard/admin/kelola-data/kelas/edit/<int:id_kelas>', methods=['GET', 'POST'])
def edit_kelas(id_kelas): # Ganti 'nim' menjadi 'kodemk'
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Sesuaikan dengan kolom DB Anda (kd_mk adalah ID, tidak diubah)
        nama_kelas_baru = request.form['nama_kelas']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            # Sesuaikan Query UPDATE
            cursor.execute("UPDATE kelas SET nama_kelas = %s,  WHERE id_kelas = %s",
                           (nama_kelas_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
            
            return redirect(url_for('admin_kelola_kelas'))

    # (Method GET)
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 
        
        # Sesuaikan Query SELECT
        cursor.execute("SELECT * FROM kelas WHERE id_kelas = %s", (id_kelas))
        kelas_data = cursor.fetchone() 
        
        if not kelas_data:
            return "Data kelas tidak ditemukan.", 404
            
        # Kirim ke file HTML dan variabel yang baru
        return render_template('admin/edit_kelas_form.html', 
                               user=session['username'], 
                               kelas=kelas_data) 
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        cursor.close()
        conn.close()

#Kelola Angkatan
# Kelola Angkatan
@app.route('/dashboard/admin/kelola-data/angkatan')
def admin_kelola_angkatan():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM angkatan") 
            daftar_angkatan = cursor.fetchall()
        except Exception as e:
            print(f"Error reading angkatan database: {e}")
            return "Terjadi error saat mengambil data."
        finally:
            cursor.close()
            conn.close()
        return render_template('admin/kelola_angkatan_list.html', 
                               user=session['username'], 
                               daftar_angkatan=daftar_angkatan)
    return redirect(url_for('login'))


@app.route('/dashboard/admin/kelola-data/angkatan/edit/<int:id_angkatan>', methods=['GET', 'POST'])
def edit_angkatan(id_angkatan):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama_angkatan_baru = request.form['tahun']
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE angkatan SET tahun = %s WHERE id_angkatan = %s",
                           (nama_angkatan_baru, id_angkatan))
            conn.commit()
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_kelola_angkatan'))

    # GET method
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM angkatan WHERE id_angkatan = %s", (id_angkatan,))
        angkatan_data = cursor.fetchone()
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        cursor.close()
        conn.close()

    if not angkatan_data:
        return "Data angkatan tidak ditemukan.", 404

    return render_template('admin/edit_angkatan_form.html',
                           user=session['username'],
                           angkatan=angkatan_data)


@app.route('/dashboard/admin/kelola-data/angkatan/tambah', methods=['GET', 'POST'])
def tambah_angkatan():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        tahun_angkatan_baru = request.form['tahun']
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO angkatan (tahun) VALUES (%s)", (tahun_angkatan_baru,))
            conn.commit()
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_kelola_angkatan'))

    return render_template('admin/tambah_angkatan_form.html', user=session['username'])


@app.route('/dashboard/admin/kelola-data/angkatan/hapus/<int:id_angkatan>')
def hapus_angkatan(id_angkatan):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM angkatan WHERE id_angkatan = %s", (id_angkatan,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_kelola_angkatan'))
 

# ================================= PAGE KELOLA AKUN =======================================
@app.route('/dashboard/admin/kelola-akun')
def admin_kelola_akun():
    if session.get('role') == 'admin':
        return render_template('admin/kelola-akun.html', user=session['username'])
    return redirect(url_for('login'))
# AKUN DOSEN
@app.route('/dashboard/admin/kelola-akun/dosen')
def admin_akun_dosen():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM akun WHERE nip_dosen IS NOT NULL")
        daftar_akun = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template(
            'admin/kelola_akun_dosen_list.html', 
            user=session['username'], 
            daftar_akun=daftar_akun
        )
    except Exception as e:
        print(f"Error reading dosen account data: {e}")
        return "Terjadi error saat mengambil data."
@app.route('/dashboard/admin/kelola-akun/dosen/hapus/<string:username>')
def hapus_akun_dosen(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM akun WHERE Username = %s", (username,))
        conn.commit()
        
    except Exception as e:
        print(f"Error deleting account: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_akun_dosen'))
@app.route('/dashboard/admin/kelola-akun/dosen/tambah', methods=['GET', 'POST'])
def tambah_akun_dosen():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nip_dosen = request.form['nip_dosen']
        
        try:
            cursor.execute("INSERT INTO akun (Username, Password, nip_dosen) VALUES (%s, %s, %s)",
                           (username, password, nip_dosen))
            conn.commit()
        except Exception as e:
            print(f"Error inserting account: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_dosen'))
    try:
        cursor.execute("SELECT NIP, Nama FROM dosen")
        daftar_dosen = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching dosen list: {e}")
        daftar_dosen = [] 
    finally:
        cursor.close()
        conn.close()
    return render_template('admin/tambah_akun_dosen_form.html', 
                           user=session['username'], 
                           daftar_dosen=daftar_dosen) 
@app.route('/dashboard/admin/kelola-akun/dosen/edit/<string:username>', methods=['GET', 'POST'])
def edit_akun_dosen(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        password = request.form['password']
        nip_dosen = request.form['nip_dosen']
        
        try:
            cursor.execute("UPDATE akun SET Password = %s, nip_dosen = %s WHERE Username = %s",
                           (password, nip_dosen, username))
            conn.commit()
        except Exception as e:
            print(f"Error updating account: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_dosen'))
    try:
        cursor.execute("SELECT * FROM akun WHERE Username = %s", (username,))
        akun_data = cursor.fetchone()
        
        cursor.execute("SELECT NIP, Nama FROM dosen")
        daftar_dosen = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Error mengambil data."
    finally:
        cursor.close()
        conn.close()
        
    if not akun_data:
        return "Akun tidak ditemukan.", 404
    return render_template('admin/edit_akun_dosen_form.html', 
                           user=session['username'], 
                           akun=akun_data,
                           daftar_dosen=daftar_dosen)
# KELOLA AKUN MAHASISWA
@app.route('/dashboard/admin/kelola-akun/mahasiswa')
def admin_akun_mahasiswa():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM akun WHERE nim_mahasiswa IS NOT NULL")
        daftar_akun = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template(
            'admin/kelola_akun_mahasiswa_list.html', 
            user=session['username'], 
            daftar_akun=daftar_akun
        )
    except Exception as e:
        print(f"Error reading mahasiswa account data: {e}")
        return "Terjadi error saat mengambil data."
@app.route('/dashboard/admin/kelola-akun/mahasiswa/hapus/<string:username>')
def hapus_akun_mahasiswa(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM akun WHERE Username = %s", (username,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting account: {e}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_akun_mahasiswa'))
@app.route('/dashboard/admin/kelola-akun/mahasiswa/tambah', methods=['GET', 'POST'])
def tambah_akun_mahasiswa():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nim_mahasiswa = request.form['nim_mahasiswa']
        
        try:
            cursor.execute("INSERT INTO akun (Username, Password, nim_mahasiswa) VALUES (%s, %s, %s)",
                           (username, password, nim_mahasiswa))
            conn.commit()
        except Exception as e:
            print(f"Error inserting account: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_mahasiswa'))
    try:
        cursor.execute("SELECT NIM, Nama FROM mahasiswa") 
        daftar_mahasiswa = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching mahasiswa list: {e}")
        daftar_mahasiswa = []
    finally:
        cursor.close()
        conn.close()
        
    return render_template('admin/tambah_akun_mahasiswa_form.html', 
                           user=session['username'], 
                           daftar_mahasiswa=daftar_mahasiswa)
@app.route('/dashboard/admin/kelola-akun/mahasiswa/edit/<string:username>', methods=['GET', 'POST'])
def edit_akun_mahasiswa(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        password = request.form['password']
        nim_mahasiswa = request.form['nim_mahasiswa']
        
        try:
            cursor.execute("UPDATE akun SET Password = %s, nim_mahasiswa = %s WHERE Username = %s",
                           (password, nim_mahasiswa, username))
            conn.commit()
        except Exception as e:
            print(f"Error updating account: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_mahasiswa'))
    try:
        cursor.execute("SELECT * FROM akun WHERE Username = %s", (username,))
        akun_data = cursor.fetchone()
        cursor.execute("SELECT NIM, Nama FROM mahasiswa")
        daftar_mahasiswa = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Error mengambil data."
    finally:
        cursor.close()
        conn.close()
        
    if not akun_data:
        return "Akun tidak ditemukan.", 404
        
    return render_template('admin/edit_akun_mahasiswa_form.html', 
                           user=session['username'], 
                           akun=akun_data,
                           daftar_mahasiswa=daftar_mahasiswa)
    
# KELOLA AKUN KAPRODI
@app.route('/dashboard/admin/kelola-akun/kaprodi')
def admin_akun_kaprodi():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM akun WHERE nip_kaprodi IS NOT NULL")
        daftar_akun = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template(
            'admin/kelola_akun_kaprodi_list.html', 
            user=session['username'], 
            daftar_akun=daftar_akun
        )
    except Exception as e:
        print(f"Error reading kaprodi account data: {e}")
        return "Terjadi error saat mengambil data."
@app.route('/dashboard/admin/kelola-akun/kaprodi/hapus/<string:username>')
def hapus_akun_kaprodi(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM akun WHERE Username = %s", (username,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting account: {e}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_akun_kaprodi'))
@app.route('/dashboard/admin/kelola-akun/kaprodi/tambah', methods=['GET', 'POST'])
def tambah_akun_kaprodi():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        nip_kaprodi = request.form['nip_kaprodi']
        
        try:
            cursor.execute("INSERT INTO akun (Username, Password, nip_kaprodi) VALUES (%s, %s, %s)",
                           (username, password, nip_kaprodi))
            conn.commit()
        except Exception as e:
            print(f"Error inserting account: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_kaprodi'))

    try:
        cursor.execute("SELECT NIP, Nama FROM kaprodi") 
        daftar_kaprodi = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching kaprodi list: {e}")
        daftar_kaprodi = []
    finally:
        cursor.close()
        conn.close()
        
    return render_template('admin/tambah_akun_kaprodi_form.html', 
                           user=session['username'], 
                           daftar_kaprodi=daftar_kaprodi)
@app.route('/dashboard/admin/kelola-akun/kaprodi/edit/<string:username>', methods=['GET', 'POST'])
def edit_akun_kaprodi(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        password = request.form['password']
        nip_kaprodi = request.form['nip_kaprodi']
        
        try:
            cursor.execute("UPDATE akun SET Password = %s, nip_kaprodi = %s WHERE Username = %s",
                           (password, nip_kaprodi, username))
            conn.commit()
        except Exception as e:
            print(f"Error updating account: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_kaprodi'))
    try:
        cursor.execute("SELECT * FROM akun WHERE Username = %s", (username,))
        akun_data = cursor.fetchone()
        cursor.execute("SELECT NIP, Nama FROM kaprodi")
        daftar_kaprodi = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Error mengambil data."
    finally:
        cursor.close()
        conn.close()
        
    if not akun_data:
        return "Akun tidak ditemukan.", 404
        
    return render_template('admin/edit_akun_kaprodi_form.html', 
                           user=session['username'], 
                           akun=akun_data,
                           daftar_kaprodi=daftar_kaprodi)

#============================ PAGE KELOLA BIMBINGAN ==================================
@app.route('/dashboard/admin/kelola-bimbingan')
def admin_kelola_bimbingan():
    if session.get('role') == 'admin':
        return render_template('admin/kelola-bimbingan.html', user=session['username'])
    return redirect(url_for('login'))


# KELOLA JADWAL
@app.route('/dashboard/admin/kelola-jadwal')
def admin_kelola_jadwal():
    if session.get('role') == 'admin':
        return render_template('admin/kelola-jadwal.html', user=session['username'])
    return redirect(url_for('login'))
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)