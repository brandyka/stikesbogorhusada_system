from flask import Flask, render_template, request, redirect, session, url_for,send_from_directory, flash, jsonify
from db_conn import create_connection
import os
from datetime import datetime, date
from pyngrok import ngrok
from werkzeug.utils import secure_filename
frontend_path = os.path.join(os.path.dirname(__file__), '../frontend')


app = Flask(__name__, template_folder=frontend_path)
app.secret_key = "secret123"

#FOTO MAHASISWA
UPLOAD_FOLDER = 'static/uploads/foto' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Fungsi bantuan untuk mengecek ekstensi file
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
#DOKUMEN PENELITIAN
# Gunakan path yang sudah Anda definisikan:
UPLOAD_FOLDER_PATH = 'static/dokumen_penelitian' 

# 1. SET KE DALAM CONFIG FLASK
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_PATH

# 2. OPTIONAL: Tambahkan batas ukuran file (sangat disarankan)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max
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
        
    conn = None
    cursor = None
    try:
        username = session.get('username')
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        sql_query = """
             SELECT 
                 m.NIM, 
                 m.Nama, 
                 m.foto,              -- TAMBAHKAN KOLOM FOTO DI SINI
                 m.id_kelas, 
                 m.id_angkatan, 
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

        if not mahasiswa_data:
            session.clear()
            flash("Data profil tidak ditemukan.", 'error') 
            return redirect(url_for('login'))
            
        session['nim_mahasiswa'] = mahasiswa_data['NIM']
        session['id_kelas'] = mahasiswa_data['id_kelas']
        session['id_angkatan'] = mahasiswa_data['id_angkatan']
            
        return render_template('mahasiswa/dashboard_mhs.html', 
                               user=username, 
                               data=mahasiswa_data) 
    except Exception as e:
        print(f"Error fetching mahasiswa dashboard data: {e}")
        flash("Terjadi error saat mengambil data profil.", 'error') 
        return redirect(url_for('login')) 
    
    finally: 
        if cursor:
            cursor.close()
        if conn:
            conn.close()
#================================= PAGE JADWAL ==========================================
from datetime import date, datetime
# Asumsi create_connection, url_for, flash, render_template, dan session/request sudah diimport

@app.route('/dashboard/mahasiswa/jadwal')
def jadwal_mahasiswa():
    if session.get('role') != 'mahasiswa':
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    try:
        username = session.get('username')
        nim_mhs = session.get('nim_mahasiswa')
        id_kelas_mhs = session.get('id_kelas')
        id_angkatan_mhs = session.get('id_angkatan')

        # Memastikan data kelas/angkatan ada di session
        if not all([nim_mhs, id_kelas_mhs, id_angkatan_mhs]):
            conn_check = create_connection()
            cursor_check = conn_check.cursor(dictionary=True)
            sql_get_ids = "SELECT m.NIM, m.id_kelas, m.id_angkatan FROM akun a JOIN mahasiswa m ON a.nim_mahasiswa = m.NIM WHERE a.Username = %s"
            cursor_check.execute(sql_get_ids, (username,))
            mahasiswa_ids = cursor_check.fetchone()
            cursor_check.close()
            conn_check.close()
            if mahasiswa_ids:
                nim_mhs, id_kelas_mhs, id_angkatan_mhs = mahasiswa_ids['NIM'], mahasiswa_ids['id_kelas'], mahasiswa_ids['id_angkatan']
                session['nim_mahasiswa'], session['id_kelas'], session['id_angkatan'] = nim_mhs, id_kelas_mhs, id_angkatan_mhs
            else:
                flash("Data mahasiswa tidak ditemukan.", 'error')
                return redirect(url_for('login'))

        
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        today_date = date.today()

        # 1. Query untuk Jadwal Reguler (Tampilan Utama)
        sql_get_jadwal = """
            SELECT 
                j.id_jadwal, j.hari, 
                TIME_FORMAT(j.jam_mulai, '%H:%i') AS jam_mulai_f, 
                TIME_FORMAT(j.jam_selesai, '%H:%i') AS jam_selesai_f, 
                j.ruangan,
                mk.nama_matkul,
                d.Nama AS nama_dosen
            FROM jadwal j
            LEFT JOIN matkul mk ON j.kd_mk = mk.kd_mk
            LEFT JOIN dosen d ON j.nip_dosen = d.NIP
            WHERE j.id_kelas = %s AND j.id_angkatan = %s
            ORDER BY FIELD(j.hari, 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'), j.jam_mulai
        """
        cursor.execute(sql_get_jadwal, (id_kelas_mhs, id_angkatan_mhs))
        daftar_jadwal = cursor.fetchall()
        
        # 2. Query untuk Pertemuan yang Absensinya DIBUKA HARI INI (Reguler atau Pengganti)
        sql_get_pertemuan_hari_ini = """
            SELECT 
                p.id_jadwal, p.id_pertemuan, p.materi, p.pertemuan_ke,
                am.status_kehadiran AS status_kehadiran_saya,
                TIME_FORMAT(p.jam_mulai, '%H:%i') AS jam_mulai_p, 
                TIME_FORMAT(p.jam_selesai, '%H:%i') AS jam_selesai_p,
                p.ruangan AS ruangan_p
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            LEFT JOIN absensi_mahasiswa am ON p.id_pertemuan = am.id_pertemuan
                                             AND am.nim_mahasiswa = %s
            WHERE j.id_kelas = %s AND j.id_angkatan = %s
              AND p.status_absensi = 'dibuka'
              AND p.tanggal = %s 
              AND p.status_pertemuan IN ('Reguler', 'Disetujui')
            ORDER BY p.pertemuan_ke ASC
        """
    
        cursor.execute(sql_get_pertemuan_hari_ini, (nim_mhs, id_kelas_mhs, id_angkatan_mhs, today_date))
        pertemuan_hari_ini_list = cursor.fetchall()
        
        # Mapping semua pertemuan yang dibuka hari ini ke jadwal regulernya
        pertemuan_map = {}
        for j in daftar_jadwal:
            pertemuan_map[j['id_jadwal']] = [] 
            
        for p in pertemuan_hari_ini_list:
            jadwal_id = p['id_jadwal']
            if jadwal_id in pertemuan_map:
                pertemuan_map[jadwal_id].append(p)
        
        # 3. Query untuk Perubahan Jadwal Mendatang (Pertemuan Pengganti yang Disetujui)
        # *** PERBAIKAN PADA WHERE CLAUSE ***
        sql_query_perubahan = """
            SELECT
                p.tanggal_asli,
                p.tanggal AS tanggal_pengganti, 
                TIME_FORMAT(p.jam_mulai, '%H:%i') AS jam_mulai_pengganti_f, 
                TIME_FORMAT(p.jam_selesai, '%H:%i') AS jam_selesai_pengganti_f, 
                p.ruangan AS ruangan_pengganti, 
                j.hari AS hari_asli,
                TIME_FORMAT(j.jam_mulai, '%H:%i') AS jam_mulai_asli_f,
                TIME_FORMAT(j.jam_selesai, '%H:%i') AS jam_selesai_asli_f,
                j.ruangan AS ruangan_asli,
                mk.nama_matkul,
                d.Nama AS nama_dosen
            FROM pertemuan p 
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal 
            JOIN matkul mk ON j.kd_mk = mk.kd_mk
            JOIN dosen d ON j.nip_dosen = d.NIP
            WHERE j.id_kelas = %s AND j.id_angkatan = %s
              AND p.status_pertemuan = 'Disetujui' 
              AND p.tanggal >= %s  
            ORDER BY p.tanggal ASC
        """
        cursor.execute(sql_query_perubahan, (id_kelas_mhs, id_angkatan_mhs, today_date))
        perubahan_list = cursor.fetchall()
        
        # Penentuan hari ini untuk tampilan (Frontend)
        days = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
        day_index = today_date.weekday() 
        hari_ini = days[day_index]

        return render_template('mahasiswa/jadwal_mhs.html', 
                               user=username, 
                               daftar_jadwal=daftar_jadwal,      
                               perubahan_list=perubahan_list,    
                               pertemuan_map=pertemuan_map,      
                               hari_ini=hari_ini)

    except Exception as e:
        print(f"Error fetching jadwal mahasiswa: {e}")
        flash("Terjadi error saat mengambil data jadwal.", 'error')
        return redirect(url_for('dashboard_mahasiswa')) 
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/dashboard/mahasiswa/absen', methods=['POST'])
def mahasiswa_absen():
    """
    Route untuk mahasiswa melakukan absensi (mencatat kehadiran)
    [+] DIPERBARUI UNTUK MENERIMA STATUS (HADIR, SAKIT, IZIN)
    [+] MEMPERBAIKI BUG DUPLIKASI DENGAN LOGIKA UPDATE/INSERT
    """
    if session.get('role') != 'mahasiswa' or 'nim_mahasiswa' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        nim_mahasiswa = session['nim_mahasiswa']
        id_pertemuan = request.form.get('id_pertemuan')
        
        status_kehadiran_baru = request.form.get('status_kehadiran')
        
        if not id_pertemuan:
            flash("Data pertemuan tidak valid.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))

        if status_kehadiran_baru not in ['hadir', 'sakit', 'izin']:
            flash("Status kehadiran tidak valid.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))
            
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql_cek_pertemuan = """
            SELECT p.id_pertemuan, p.status_absensi, p.tanggal,
                   j.id_kelas, j.id_angkatan
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            WHERE p.id_pertemuan = %s
        """
        cursor.execute(sql_cek_pertemuan, (id_pertemuan,))
        pertemuan = cursor.fetchone()
        
        if not pertemuan:
            flash("Pertemuan tidak ditemukan.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))
        
        if pertemuan['status_absensi'] != 'dibuka':
            flash("Absensi sudah ditutup oleh dosen.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))
        
        if pertemuan['tanggal'] != date.today():
            flash("Absensi hanya bisa dilakukan pada hari pertemuan.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))
        
        id_kelas_mhs = session.get('id_kelas')
        id_angkatan_mhs = session.get('id_angkatan')
        
        if pertemuan['id_kelas'] != id_kelas_mhs or pertemuan['id_angkatan'] != id_angkatan_mhs:
            flash("Anda tidak terdaftar di kelas ini.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))
        
        
        waktu_sekarang = datetime.now()

        sql_cek_absen = """
            SELECT id_absensi
            FROM absensi_mahasiswa
            WHERE id_pertemuan = %s AND nim_mahasiswa = %s
        """
        cursor.execute(sql_cek_absen, (id_pertemuan, nim_mahasiswa))
        existing_absen = cursor.fetchone()
        
        if existing_absen:
            sql_update = """
                UPDATE absensi_mahasiswa
                SET status_kehadiran = %s, waktu_absen = %s
                WHERE id_absensi = %s
            """
            cursor.execute(sql_update, (status_kehadiran_baru, waktu_sekarang, existing_absen['id_absensi']))
        
        else:
            sql_insert = """
                INSERT INTO absensi_mahasiswa (id_pertemuan, nim_mahasiswa, status_kehadiran, waktu_absen)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_insert, (id_pertemuan, nim_mahasiswa, status_kehadiran_baru, waktu_sekarang))

        conn.commit()

        
        flash(f"Absensi berhasil! Anda tercatat '{status_kehadiran_baru}'.", 'success')
        return redirect(url_for('jadwal_mahasiswa'))
    
    except Exception as e:
        print(f"Error mahasiswa absen: {e}")
        if conn:
            conn.rollback()
        flash("Terjadi error saat melakukan absensi.", 'error')
        return redirect(url_for('jadwal_mahasiswa'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/dashboard/mahasiswa/rekap/<int:id_jadwal>')
def rekap_absen_matkul(id_jadwal):
    """
    Menampilkan halaman rekap absensi untuk 1 mata kuliah 
    bagi mahasiswa yang sedang login.
    """
    if session.get('role') != 'mahasiswa' or 'nim_mahasiswa' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        nim_mahasiswa = session['nim_mahasiswa']
        
        conn = create_connection()
        if not conn:
            flash("Koneksi database gagal.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))
            
        cursor = conn.cursor(dictionary=True)


        sql_info_matkul = """
            SELECT 
                mk.nama_matkul, 
                d.Nama AS nama_dosen
            FROM jadwal j
            JOIN matkul mk ON j.kd_mk = mk.kd_mk
            JOIN dosen d ON j.nip_dosen = d.NIP
            WHERE j.id_jadwal = %s
        """
        cursor.execute(sql_info_matkul, (id_jadwal,))
        info_matkul = cursor.fetchone()

        if not info_matkul:
            flash("Mata kuliah tidak ditemukan.", 'error')
            return redirect(url_for('jadwal_mahasiswa'))


        sql_rekap = """
            SELECT 
                p.pertemuan_ke,
                p.tanggal,
                p.materi,
                p.status_absensi,
                COALESCE(am.status_kehadiran, 'alpa') AS status_kehadiran_saya
            FROM pertemuan p
            LEFT JOIN absensi_mahasiswa am 
                ON p.id_pertemuan = am.id_pertemuan 
                AND am.nim_mahasiswa = %s
            WHERE p.id_jadwal = %s
            ORDER BY p.pertemuan_ke ASC
        """
        cursor.execute(sql_rekap, (nim_mahasiswa, id_jadwal))
        rekap_absensi = cursor.fetchall()

        total_pertemuan = len(rekap_absensi)
        total_hadir = sum(1 for rekap in rekap_absensi if rekap['status_kehadiran_saya'] == 'hadir')
        total_izin = sum(1 for rekap in rekap_absensi if rekap['status_kehadiran_saya'] == 'izin')
        total_sakit = sum(1 for rekap in rekap_absensi if rekap['status_kehadiran_saya'] == 'sakit')
        total_alpa = sum(1 for rekap in rekap_absensi if rekap['status_kehadiran_saya'] == 'alpa')

        statistik = {
            'hadir': total_hadir,
            'izin': total_izin,
            'sakit': total_sakit,
            'alpa': total_alpa,
            'total': total_pertemuan
        }
        
        return render_template('mahasiswa/rekap_absen_matkul.html',
                               info_matkul=info_matkul,
                               rekap_absensi=rekap_absensi,
                               statistik=statistik,
                               user=session.get('username'))

    except Exception as e:
        print(f"Error fetching rekap absensi: {e}")
        flash("Terjadi error saat mengambil data rekap absensi.", 'error')
        return redirect(url_for('jadwal_mahasiswa'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ======================================================
# ---- ROUTE: DASHBOARD MAHASISWA - INFO PEMBIMBING
# ======================================================
@app.route('/dashboard/mahasiswa/dosen-pembimbing')
def mahasiswa_dosen_pembimbing():
    """
    Menampilkan daftar dosen pembimbing untuk mahasiswa yang sedang login.
    Menggunakan NIM yang sudah tersimpan di sesi ('nim_mahasiswa').
    """
    # 1. Autentikasi dan Otorisasi
    if session.get('role') != 'mahasiswa':
        return redirect(url_for('login'))
    
    # *** PERBAIKAN UTAMA: Ambil NIM dari 'nim_mahasiswa' yang sudah benar ***
    nim_mahasiswa = session.get('nim_mahasiswa') 
    
    if not nim_mahasiswa:
        # Jika NIM belum ada, arahkan kembali ke dashboard utama untuk memicu penyimpanan NIM
        return redirect(url_for('dashboard_mahasiswa')) 

    db = create_connection()
    cursor = db.cursor(dictionary=True)

    dosen_pembimbing = []
    mhs_info = {'Nama': 'N/A'}

    try:
        # 2. Query Data Mahasiswa (untuk judul/info)
        # Gunakan 'nim_mahasiswa' yang sudah pasti ada
        cursor.execute("SELECT Nama FROM mahasiswa WHERE NIM = %s", (nim_mahasiswa,))
        mhs_info = cursor.fetchone()
        
        # 3. Query Data Dosen Pembimbing
        query = """
        SELECT
            d.NIP,
            d.Nama AS NamaDosen,
            d.ProgramStudi,
            b.jenis_bimbingan AS JenisBimbingan,
            b.id_bimbingan
        FROM bimbingan b
        INNER JOIN dosen d ON b.NIP = d.NIP
        WHERE b.NIM = %s
        ORDER BY d.Nama ASC;
        """
        cursor.execute(query, (nim_mahasiswa,))
        dosen_pembimbing = cursor.fetchall()

    except Exception as e:
        print(f"Error Mahasiswa Dosen Pembimbing: {e}")
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

    return render_template(
        'mahasiswa/info-pembimbing.html',
        mahasiswa=mhs_info if mhs_info else {'Nama': 'N/A'},
        dosen_pembimbing=dosen_pembimbing,
        user_nim=nim_mahasiswa
    )


# ======================================================
# ---- ROUTE: INPUT PERMINTAAN BIMBINGAN (MAHASISWA)
# ======================================================

@app.route('/dashboard/mahasiswa/bimbingan/input', methods=['GET', 'POST'])
def mahasiswa_input_bimbingan():
    """
    Menampilkan formulir input dan memproses pengajuan permintaan bimbingan.
    """
    if session.get('role') != 'mahasiswa' or 'nim_mahasiswa' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))
    
    nim_mahasiswa = session.get('nim_mahasiswa')
    conn = None
    cursor = None
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Ambil data Dosen Pembimbing untuk pilihan di formulir
        # Hanya mahasiswa yang punya dosen pembimbing yang boleh mengajukan
        sql_get_pembimbing = """
            SELECT
                b.id_bimbingan,
                b.jenis_bimbingan,
                d.Nama AS nama_dosen
            FROM bimbingan b
            JOIN dosen d ON b.NIP = d.NIP
            WHERE b.NIM = %s
            ORDER BY b.jenis_bimbingan ASC
        """
        cursor.execute(sql_get_pembimbing, (nim_mahasiswa,))
        list_pembimbing = cursor.fetchall()
        
        if not list_pembimbing:
            flash("Anda belum memiliki dosen pembimbing yang terdaftar. Tidak bisa mengajukan bimbingan.", 'warning')
            return redirect(url_for('mahasiswa_dosen_pembimbing'))

        if request.method == 'POST':
            # ==================================
            # PROSES PENGAJUAN (METODE POST)
            # ==================================
            
            # Ambil data dari formulir
            id_bimbingan = request.form.get('id_bimbingan') # ID yang menghubungkan Mahasiswa-Dosen
            topik_bimbingan = request.form.get('topik_bimbingan').strip()
            deskripsi_kebutuhan = request.form.get('deskripsi_kebutuhan').strip()
            
            # Validasi Input
            if not all([id_bimbingan, topik_bimbingan, deskripsi_kebutuhan]):
                flash("Semua kolom harus diisi.", 'error')
                return render_template('mahasiswa/input_bimbingan_mhs.html', list_pembimbing=list_pembimbing)
            
            # Cek apakah id_bimbingan valid dan milik mahasiswa ini
            is_valid_bimbingan = any(str(p['id_bimbingan']) == id_bimbingan for p in list_pembimbing)
            if not is_valid_bimbingan:
                flash("ID Bimbingan tidak valid. Harap pilih dari daftar yang tersedia.", 'error')
                return render_template('mahasiswa/input_bimbingan_mhs.html', list_pembimbing=list_pembimbing)
            
            
            # Query INSERT ke tabel permintaan_bimbingan
            sql_insert = """
                INSERT INTO permintaan_bimbingan 
                (id_bimbingan, topik_bimbingan, deskripsi_kebutuhan, status_permintaan, tanggal_pengajuan)
                VALUES (%s, %s, %s, 'Menunggu Respon Dosen', %s)
            """
            
            cursor.execute(sql_insert, (
                id_bimbingan, 
                topik_bimbingan, 
                deskripsi_kebutuhan, 
                datetime.now() # Menggunakan waktu saat ini
            ))
            
            conn.commit()
            
            flash("Permintaan bimbingan berhasil diajukan! Menunggu respon dari dosen.", 'success')
            return redirect(url_for('mahasiswa_riwayat_bimbingan'))
            

        # ==================================
        # TAMPILKAN FORMULIR (METODE GET)
        # ==================================
        return render_template('mahasiswa/input_bimbingan_mhs.html', 
                               list_pembimbing=list_pembimbing)
        
    except Exception as e:
        print(f"Error Mahasiswa Input Bimbingan: {e}")
        if conn: conn.rollback()
        flash("Terjadi error saat memproses permintaan bimbingan.", 'error')
        # Jika terjadi error saat POST, kembalikan ke GET dengan data yang mungkin masih ada
        return render_template('mahasiswa/input_bimbingan_mhs.html', list_pembimbing=list_pembimbing) 
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ======================================================
# ---- ROUTE: RIWAYAT PERMINTAAN BIMBINGAN (MAHASISWA)
# ======================================================

@app.route('/dashboard/mahasiswa/bimbingan/riwayat')
def mahasiswa_riwayat_bimbingan():
    """
    Menampilkan daftar riwayat permintaan bimbingan yang pernah diajukan.
    (PERBAIKAN: Menggunakan TIME_FORMAT untuk menghindari timedelta error)
    """
    if session.get('role') != 'mahasiswa' or 'nim_mahasiswa' not in session:
        return redirect(url_for('login'))
        
    nim_mahasiswa = session.get('nim_mahasiswa')
    conn = None
    cursor = None
    riwayat_bimbingan = []

    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query untuk mengambil semua riwayat permintaan bimbingan
        sql_query = """
            SELECT 
                pb.id_permintaan,
                pb.topik_bimbingan,
                pb.status_permintaan,
                pb.tanggal_pengajuan,
                pb.tanggal_bimbingan,
                -- PERBAIKAN: Konversi waktu menjadi string HH:MM
                TIME_FORMAT(pb.waktu_mulai, '%H:%i') AS waktu_mulai,
                TIME_FORMAT(pb.waktu_selesai, '%H:%i') AS waktu_selesai,
                d.Nama AS nama_dosen,
                b.jenis_bimbingan
            FROM permintaan_bimbingan pb
            JOIN bimbingan b ON pb.id_bimbingan = b.id_bimbingan
            JOIN dosen d ON b.NIP = d.NIP
            WHERE b.NIM = %s
            ORDER BY pb.tanggal_pengajuan DESC
        """
        cursor.execute(sql_query, (nim_mahasiswa,))
        riwayat_bimbingan = cursor.fetchall()
        
        return render_template('mahasiswa/riwayat_bimbingan_mhs.html', 
                               riwayat=riwayat_bimbingan,
                               user=session.get('username')) 

    except Exception as e:
        print(f"Error Mahasiswa Riwayat Bimbingan: {e}")
        flash("Terjadi error saat mengambil data riwayat bimbingan.", 'error')
        return redirect(url_for('dashboard_mahasiswa')) 
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ======================================================
# ---- ROUTE: DETAIL PERMINTAAN BIMBINGAN (MAHASISWA)
# ======================================================

@app.route('/dashboard/mahasiswa/bimbingan/detail/<int:id_permintaan>')
def mahasiswa_detail_bimbingan(id_permintaan):
    """
    Menampilkan detail spesifik dari permintaan bimbingan, termasuk jadwal/alasan dari dosen.
    """
    if session.get('role') != 'mahasiswa' or 'nim_mahasiswa' not in session:
        return redirect(url_for('login'))
        
    nim_mahasiswa = session.get('nim_mahasiswa')
    conn = None
    cursor = None
    detail = None

    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query detail permintaan dan memastikan permintaan itu milik mahasiswa yang login
        sql_query = """
            SELECT 
                pb.*,
                d.Nama AS nama_dosen,
                b.jenis_bimbingan
            FROM permintaan_bimbingan pb
            JOIN bimbingan b ON pb.id_bimbingan = b.id_bimbingan
            JOIN dosen d ON b.NIP = d.NIP
            WHERE pb.id_permintaan = %s AND b.NIM = %s
        """
        cursor.execute(sql_query, (id_permintaan, nim_mahasiswa))
        detail = cursor.fetchone()
        
        if not detail:
            flash("Detail permintaan bimbingan tidak ditemukan atau bukan milik Anda.", 'error')
            return redirect(url_for('mahasiswa_riwayat_bimbingan'))

        return render_template('mahasiswa/detail_bimbingan_mhs.html', 
                               detail=detail) 

    except Exception as e:
        print(f"Error Mahasiswa Detail Bimbingan: {e}")
        flash("Terjadi error saat mengambil detail bimbingan.", 'error')
        return redirect(url_for('mahasiswa_riwayat_bimbingan'))
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
#========================== DOSEN SECTION ==============================
#=======================================================================
@app.route('/dashboard/dosen')
def dashboard_dosen():
    """
    Halaman dashboard utama dosen (Beranda).
    """
    if session.get('role') != 'dosen':
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    try:
        username = session.get('username')
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('login'))
        cursor = conn.cursor(dictionary=True)
        
        sql_query = """
            SELECT 
                d.NIP, 
                d.Nama, 
                d.ProgramStudi
            FROM akun act
            JOIN dosen d ON act.nip_dosen = d.NIP
            WHERE act.Username = %s
        """
        cursor.execute(sql_query, (username,))
        dosen_data = cursor.fetchone()

        if not dosen_data:
            session.clear()
            flash("Data profil dosen tidak ditemukan.", 'error')
            return redirect(url_for('login'))
        
        session['nip_dosen'] = dosen_data['NIP']
                
        return render_template('dosen/dashboard_dosen.html', 
                               user=username, 
                               data=dosen_data) 
    
    except Exception as e:
        print(f"Error fetching dosen dashboard data: {e}")
        flash("Terjadi error saat mengambil data profil dosen.", 'error')
        return redirect(url_for('login'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/dashboard/dosen/jadwal')
def jadwal_dosen():
    """
    Halaman untuk menampilkan daftar jadwal mengajar dosen
    DAN riwayat pengajuan (dari tabel 'pertemuan').
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    try:
        nip_dosen = session['nip_dosen']
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('dashboard_dosen'))
        cursor = conn.cursor(dictionary=True)
        
        sql_query_jadwal = """
            SELECT 
                j.id_jadwal, j.hari,
                TIME_FORMAT(j.jam_mulai, '%H:%i') AS jam_mulai_f,
                TIME_FORMAT(j.jam_selesai, '%H:%i') AS jam_selesai_f,
                j.ruangan,
                mk.nama_matkul AS nama_mk,
                k.nama_kelas,
                a.tahun
            FROM jadwal j
            LEFT JOIN matkul mk ON j.kd_mk = mk.kd_mk
            LEFT JOIN kelas k ON j.id_kelas = k.id_kelas
            LEFT JOIN angkatan a ON j.id_angkatan = a.id_angkatan
            WHERE j.nip_dosen = %s
            ORDER BY FIELD(j.hari, 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'), j.jam_mulai
        """
        cursor.execute(sql_query_jadwal, (nip_dosen,))
        jadwal_list = cursor.fetchall()
        
        sql_query_riwayat = """
            SELECT
                p.pertemuan_ke,
                p.tanggal AS tanggal_pengganti,
                p.tanggal_asli,
                p.status_pertemuan,
                p.catatan_kaprodi,
                p.created_at,
                mk.nama_matkul
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            JOIN matkul mk ON j.kd_mk = mk.kd_mk
            WHERE j.nip_dosen = %s
              AND p.status_pertemuan IN ('Diajukan', 'Disetujui', 'Ditolak')
            ORDER BY p.created_at DESC
        """
        cursor.execute(sql_query_riwayat, (nip_dosen,))
        riwayat_list = cursor.fetchall()
        
        return render_template('dosen/jadwal_dosen.html', 
                               jadwal_list=jadwal_list,
                               riwayat_list=riwayat_list) 
    
    except Exception as e:
        print(f"Error fetching jadwal dosen: {e}")
        flash(f"Terjadi error saat mengambil data jadwal: {e}", 'error')
        return redirect(url_for('dashboard_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/dashboard/dosen/jadwal/<int:id_jadwal>/pertemuan', methods=['GET', 'POST'])
def kelola_pertemuan(id_jadwal):
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))

    conn = None
    cursor = None
    nip_dosen = session['nip_dosen']
    
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('jadwal_dosen'))
        cursor = conn.cursor(dictionary=True)

  
        if request.method == 'POST':
            pertemuan_ke = request.form['pertemuan_ke']
            tanggal = request.form['tanggal'] 
            materi = request.form['materi']
            
            is_reschedule = request.form.get('is_reschedule') == 'on'

            conn.autocommit = False 

            try:
                cursor.execute("SELECT id_kelas, id_angkatan, ruangan FROM jadwal WHERE id_jadwal = %s AND nip_dosen = %s", (id_jadwal, nip_dosen))
                jadwal_info = cursor.fetchone()
                if not jadwal_info:
                    flash("Jadwal tidak ditemukan atau bukan milik Anda.", "error")
                    return redirect(url_for('jadwal_dosen'))

                id_kelas_target = jadwal_info['id_kelas']
                id_angkatan_target = jadwal_info['id_angkatan']
                ruangan_asli = jadwal_info['ruangan']


                if is_reschedule:
                    tanggal_asli = request.form['tanggal_asli']
                    alasan_perubahan = request.form['alasan_perubahan']
                    tanggal_pengganti = tanggal 
                    jam_mulai_pengganti = request.form['jam_mulai_pengganti']
                    jam_selesai_pengganti = request.form['jam_selesai_pengganti']
                    

                    ruangan_pengganti_form = request.form.get('ruangan_pengganti')
                    if ruangan_pengganti_form == "":
                        ruangan_pengganti_form = None 
                    
                    if not all([tanggal_asli, alasan_perubahan, jam_mulai_pengganti, jam_selesai_pengganti]):
                        flash("Untuk reschedule, semua field (kecuali ruangan) wajib diisi.", 'warning')
                        return redirect(url_for('kelola_pertemuan', id_jadwal=id_jadwal))

                    if jam_mulai_pengganti >= jam_selesai_pengganti:
                        flash("Jam selesai harus setelah jam mulai.", 'warning')
                        return redirect(url_for('kelola_pertemuan', id_jadwal=id_jadwal))

                    ruangan_final_check = ruangan_pengganti_form if ruangan_pengganti_form else ruangan_asli
                    sql_overlap_logic = "(%s < j.jam_selesai AND %s > j.jam_mulai)"
                    sql_overlap_logic_pertemuan = "(%s < p.jam_selesai AND %s > p.jam_mulai)" 
                    hari_to_weekday_logic = "(CASE j.hari WHEN 'Senin' THEN 0 WHEN 'Selasa' THEN 1 WHEN 'Rabu' THEN 2 WHEN 'Kamis' THEN 3 WHEN 'Jumat' THEN 4 WHEN 'Sabtu' THEN 5 WHEN 'Minggu' THEN 6 ELSE -1 END) = WEEKDAY(%s)"


                    sql_cek_kelas_default = f"SELECT j.id_jadwal, mk.nama_matkul, d.Nama AS nama_dosen FROM jadwal j LEFT JOIN matkul mk ON j.kd_mk = mk.kd_mk LEFT JOIN dosen d ON j.nip_dosen = d.NIP WHERE j.id_kelas = %s AND j.id_angkatan = %s AND {hari_to_weekday_logic} AND {sql_overlap_logic} AND j.id_jadwal != %s"
                    cursor.execute(sql_cek_kelas_default, (id_kelas_target, id_angkatan_target, tanggal_pengganti, jam_mulai_pengganti, jam_selesai_pengganti, id_jadwal))
                    tabrakan_kelas_def = cursor.fetchone()
                    if tabrakan_kelas_def:
                        flash(f"Gagal (Kelas): Kelas ini punya jadwal default lain (Matkul: {tabrakan_kelas_def['nama_matkul']} / Dosen: {tabrakan_kelas_def['nama_dosen']}) di jam tersebut.", 'error')
                        return redirect(url_for('kelola_pertemuan', id_jadwal=id_jadwal))

                    sql_insert = """
                        INSERT INTO pertemuan (id_jadwal, pertemuan_ke, tanggal, materi, 
                                           status_absensi, status_pertemuan, tanggal_asli, 
                                           alasan_perubahan, jam_mulai, jam_selesai, ruangan)
                        VALUES (%s, %s, %s, %s, 'ditutup', 'Diajukan', %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql_insert, (
                        id_jadwal, pertemuan_ke, tanggal_pengganti, materi,
                        tanggal_asli, alasan_perubahan, jam_mulai_pengganti, 
                        jam_selesai_pengganti, ruangan_pengganti_form
                    ))
                    conn.commit()
                    flash('Permintaan perubahan jadwal (reschedule) berhasil diajukan ke Kaprodi.', 'success')

  
                else:
                   
                    cursor.execute("SELECT jam_mulai, jam_selesai, ruangan FROM jadwal WHERE id_jadwal = %s", (id_jadwal,))
                    jadwal_waktu = cursor.fetchone()
                    sql_insert = """
                        INSERT INTO pertemuan (id_jadwal, pertemuan_ke, tanggal, materi, 
                                           status_absensi, status_pertemuan, 
                                           jam_mulai, jam_selesai, ruangan)
                        VALUES (%s, %s, %s, %s, 'dibuka', 'Reguler', %s, %s, %s)
                    """
                    cursor.execute(sql_insert, (
                        id_jadwal, pertemuan_ke, tanggal, materi,
                        jadwal_waktu['jam_mulai'], jadwal_waktu['jam_selesai'], jadwal_waktu['ruangan']
                    ))
                    id_pertemuan_baru = cursor.lastrowid
                    sql_get_mhs = "SELECT NIM FROM mahasiswa WHERE id_kelas = %s AND id_angkatan = %s"
                    cursor.execute(sql_get_mhs, (id_kelas_target, id_angkatan_target))
                    mahasiswa_list = cursor.fetchall()
                    if mahasiswa_list:
                        sql_insert_absen = "INSERT INTO absensi_mahasiswa (id_pertemuan, nim_mahasiswa, status_kehadiran) VALUES (%s, %s, 'alpa')"
                        data_absen = [(id_pertemuan_baru, mhs['NIM']) for mhs in mahasiswa_list]
                        cursor.executemany(sql_insert_absen, data_absen)
                    else:
                         flash('Pertemuan dibuat, namun tidak ada mahasiswa di kelas ini.', 'warning')
                    
                    conn.commit() 
                    flash('Pertemuan baru berhasil dibuat dan absensi dibuka.', 'success')
            
            except Exception as e:
                conn.rollback() 
                print(f"Error saat buat pertemuan (transaksi dibatalkan): {e}")
                flash(f'Gagal membuat pertemuan, terjadi error: {e}', 'error')
            
            finally:
                conn.autocommit = True 
            
            return redirect(url_for('kelola_pertemuan', id_jadwal=id_jadwal))

        sql_detail = """
            SELECT mk.nama_matkul, k.nama_kelas, a.tahun
            FROM jadwal j
            LEFT JOIN matkul mk ON j.kd_mk = mk.kd_mk
            LEFT JOIN kelas k ON j.id_kelas = k.id_kelas
            LEFT JOIN angkatan a ON j.id_angkatan = a.id_angkatan
            WHERE j.id_jadwal = %s AND j.nip_dosen = %s
        """
        cursor.execute(sql_detail, (id_jadwal, nip_dosen))
        detail_jadwal = cursor.fetchone()

        if not detail_jadwal:
            flash('Jadwal tidak ditemukan.', 'error')
            return redirect(url_for('jadwal_dosen'))

        sql_pertemuan = """
            SELECT 
                p.id_pertemuan, p.pertemuan_ke, p.tanggal, p.materi, 
                p.status_absensi, p.status_pertemuan, p.catatan_kaprodi,
                SUM(CASE WHEN am.status_kehadiran = 'hadir' THEN 1 ELSE 0 END) AS total_hadir,
                SUM(CASE WHEN am.status_kehadiran = 'izin' THEN 1 ELSE 0 END) AS total_izin,
                SUM(CASE WHEN am.status_kehadiran = 'sakit' THEN 1 ELSE 0 END) AS total_sakit,
                SUM(CASE WHEN am.status_kehadiran = 'alpa' THEN 1 ELSE 0 END) AS total_alpa
            FROM pertemuan p
            LEFT JOIN absensi_mahasiswa am ON p.id_pertemuan = am.id_pertemuan
            WHERE p.id_jadwal = %s
            GROUP BY p.id_pertemuan, p.pertemuan_ke, p.tanggal, p.materi, p.status_absensi, p.status_pertemuan, p.catatan_kaprodi
            ORDER BY p.pertemuan_ke
        """
        cursor.execute(sql_pertemuan, (id_jadwal,))
        pertemuan_list = cursor.fetchall()
        
        sql_get_ruangan = """
            SELECT DISTINCT ruangan 
            FROM jadwal 
            WHERE ruangan IS NOT NULL AND ruangan != '' 
            ORDER BY ruangan ASC
        """
        cursor.execute(sql_get_ruangan)
        ruangan_list = cursor.fetchall()
        
        return render_template('dosen/kelola_pertemuan.html',
                               detail_jadwal=detail_jadwal,
                               pertemuan_list=pertemuan_list,
                               ruangan_list=ruangan_list,  
                               id_jadwal=id_jadwal)

    except Exception as e:
        print(f"Error kelola pertemuan: {e}")
        flash(f"Terjadi error: {e}", 'error') 
        return redirect(url_for('jadwal_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/dashboard/dosen/pertemuan/<int:id_pertemuan>')
def detail_pertemuan(id_pertemuan):
    """
    Halaman untuk melihat daftar absensi mahasiswa untuk pertemuan spesifik.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('jadwal_dosen'))
        cursor = conn.cursor(dictionary=True)

        sql_pertemuan = """
            SELECT p.pertemuan_ke, p.tanggal, p.materi, p.status_absensi,
                   mk.nama_matkul, k.nama_kelas
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            LEFT JOIN matkul mk ON j.kd_mk = mk.kd_mk
            LEFT JOIN kelas k ON j.id_kelas = k.id_kelas
            WHERE p.id_pertemuan = %s AND j.nip_dosen = %s
        """
        cursor.execute(sql_pertemuan, (id_pertemuan, session['nip_dosen']))
        detail = cursor.fetchone()

        if not detail:
            flash('Pertemuan tidak ditemukan atau Anda tidak punya akses.', 'error')
            return redirect(url_for('jadwal_dosen'))
            
        sql_absensi = """
            SELECT m.NIM, m.Nama, am.status_kehadiran, am.waktu_absen
            FROM absensi_mahasiswa am
            JOIN mahasiswa m ON am.nim_mahasiswa = m.NIM
            WHERE am.id_pertemuan = %s
            ORDER BY m.Nama
        """
        cursor.execute(sql_absensi, (id_pertemuan,))
        absensi_list = cursor.fetchall()
        
        statistik = {
            'hadir': 0, 'izin': 0, 'sakit': 0, 'alpa': 0, 'total': 0
        }
        if absensi_list:
            statistik['total'] = len(absensi_list)
            for mhs in absensi_list:
                status = mhs['status_kehadiran']
                if status == 'hadir':
                    statistik['hadir'] += 1
                elif status == 'izin':
                    statistik['izin'] += 1
                elif status == 'sakit':
                    statistik['sakit'] += 1
                elif status == 'alpa':
                    statistik['alpa'] += 1
        
        return render_template('dosen/detail_pertemuan.html',
                               detail=detail,
                               absensi_list=absensi_list,
                               statistik=statistik, 
                               id_pertemuan=id_pertemuan)
        
    except Exception as e:
        print(f"Error detail pertemuan: {e}")
        flash("Terjadi error.", 'error')
        return redirect(url_for('jadwal_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/dashboard/dosen/pertemuan/<int:id_pertemuan>/toggle_status', methods=['POST'])
def toggle_status_absensi(id_pertemuan):
    """
    Toggle status absensi antara 'dibuka' dan 'ditutup'
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('jadwal_dosen'))
        cursor = conn.cursor(dictionary=True)
        
        sql_check = """
            SELECT p.id_pertemuan, p.status_absensi, p.id_jadwal
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            WHERE p.id_pertemuan = %s AND j.nip_dosen = %s
        """
        cursor.execute(sql_check, (id_pertemuan, session['nip_dosen']))
        pertemuan = cursor.fetchone()
        
        if not pertemuan:
            flash('Pertemuan tidak ditemukan atau Anda tidak punya akses.', 'error')
            return redirect(url_for('jadwal_dosen'))
        
        status_baru = 'ditutup' if pertemuan['status_absensi'] == 'dibuka' else 'dibuka'
        
        sql_update = "UPDATE pertemuan SET status_absensi = %s WHERE id_pertemuan = %s"
        cursor.execute(sql_update, (status_baru, id_pertemuan))
        
        conn.commit() 
        
        flash(f'Status absensi berhasil diubah menjadi "{status_baru}".', 'success')
        return redirect(url_for('kelola_pertemuan', id_jadwal=pertemuan['id_jadwal']))
    
    except Exception as e:
        print(f"Error toggle status: {e}")
        flash("Terjadi error saat mengubah status.", 'error')
        return redirect(url_for('jadwal_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/dashboard/dosen/pertemuan/<int:id_pertemuan>/hapus', methods=['POST'])
def hapus_pertemuan(id_pertemuan):
    """
    Hapus pertemuan dan semua data absensi terkait
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('jadwal_dosen'))
        cursor = conn.cursor(dictionary=True)
        
        sql_check = """
            SELECT p.id_pertemuan, p.id_jadwal
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            WHERE p.id_pertemuan = %s AND j.nip_dosen = %s
        """
        cursor.execute(sql_check, (id_pertemuan, session['nip_dosen']))
        pertemuan = cursor.fetchone()
        
        if not pertemuan:
            flash('Pertemuan tidak ditemukan atau Anda tidak punya akses.', 'error')
            return redirect(url_for('jadwal_dosen'))
        
        id_jadwal = pertemuan['id_jadwal']
        
        cursor.execute("DELETE FROM absensi_mahasiswa WHERE id_pertemuan = %s", (id_pertemuan,))
        
        cursor.execute("DELETE FROM pertemuan WHERE id_pertemuan = %s", (id_pertemuan,))
        
        conn.commit()
        flash('Pertemuan berhasil dihapus.', 'success')
        return redirect(url_for('kelola_pertemuan', id_jadwal=id_jadwal))
    
    except Exception as e:
        print(f"Error hapus pertemuan: {e}")
        flash("Terjadi error saat menghapus pertemuan.", 'error')
        return redirect(url_for('jadwal_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/dashboard/dosen/pertemuan/update_status', methods=['POST'])
def update_absensi_dosen():
    """
    Dosen mengubah status absensi seorang mahasiswa secara manual.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))

    conn = None
    cursor = None
    
    id_pertemuan = request.form.get('id_pertemuan')
    nim_mahasiswa = request.form.get('nim_mahasiswa')
    status_baru = request.form.get('status_baru')
    
    redirect_url = url_for('detail_pertemuan', id_pertemuan=id_pertemuan)
    
    if not all([id_pertemuan, nim_mahasiswa, status_baru]):
        flash("Data tidak lengkap.", 'error')
        return redirect(url_for('jadwal_dosen')) 

    if status_baru not in ['hadir', 'alpa', 'izin', 'sakit']:
        flash("Status tidak valid.", 'error')
        return redirect(redirect_url)

    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(redirect_url)
        cursor = conn.cursor(dictionary=True)
        
        sql_check = """
            SELECT p.id_pertemuan
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            WHERE p.id_pertemuan = %s AND j.nip_dosen = %s
        """
        cursor.execute(sql_check, (id_pertemuan, session['nip_dosen']))
        if not cursor.fetchone():
            flash("Anda tidak memiliki akses ke pertemuan ini.", 'error')
            return redirect(url_for('jadwal_dosen'))


        waktu_absen_val = None
        
        if status_baru == 'hadir':
            sql_get_time = "SELECT waktu_absen FROM absensi_mahasiswa WHERE id_pertemuan = %s AND nim_mahasiswa = %s"
            cursor.execute(sql_get_time, (id_pertemuan, nim_mahasiswa))
            current_absen = cursor.fetchone()
            
            if current_absen and current_absen['waktu_absen']:
                 waktu_absen_val = current_absen['waktu_absen']
            else:
                 waktu_absen_val = datetime.now()
        
 
        sql_update = """
            UPDATE absensi_mahasiswa
            SET status_kehadiran = %s, waktu_absen = %s
            WHERE id_pertemuan = %s AND nim_mahasiswa = %s
        """
        cursor.execute(sql_update, (status_baru, waktu_absen_val, id_pertemuan, nim_mahasiswa))
        conn.commit()
        
        flash(f"Status absensi untuk NIM {nim_mahasiswa} berhasil diubah.", 'success')
        return redirect(redirect_url)

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error update absensi dosen: {e}")
        flash("Terjadi error saat update data.", 'error')
        return redirect(redirect_url)
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ======================== PENELITIAN SECTION =============================
# Gunakan variabel yang didefinisikan di awal
UPLOAD_FOLDER_PATH = 'static/dokumen_penelitian' # Sesuaikan jika path berbeda

# Sesuaikan ekstensi ini dengan kebutuhan upload Anda
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'zip', 'doc', 'docx'} 

# Pastikan folder upload ada (menggunakan path yang sama)
if not os.path.exists(UPLOAD_FOLDER_PATH):
    os.makedirs(UPLOAD_FOLDER_PATH)

def allowed_file(filename):
    # ... (fungsi allowed_file)
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/dashboard/dosen/penelitian')
def penelitian_dosen():
    """
    Halaman utama penelitian dosen: menampilkan daftar penelitian
    dan link/tombol untuk input penelitian baru.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    nip_dosen = session['nip_dosen']
    
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('dashboard_dosen'))
        cursor = conn.cursor(dictionary=True)

        # Ambil daftar penelitian di mana dosen ini adalah Ketua atau Anggota
        sql_query = """
                    SELECT DISTINCT
                        p.id_penelitian,
                        p.judul_penelitian,
                        p.tahun_pelaksanaan,
                        p.status_penelitian,
                        p.nip_ketua  -- !!! KOLOM INI HARUS DIAMBIL !!!
                    FROM penelitian p
                    LEFT JOIN penelitian_anggota_dosen pad ON p.id_penelitian = pad.id_penelitian
                    WHERE p.nip_ketua = %s OR pad.nip_anggota = %s
                    ORDER BY p.tahun_pelaksanaan DESC, p.id_penelitian DESC
                """
        cursor.execute(sql_query, (nip_dosen, nip_dosen))
        penelitian_list = cursor.fetchall()

        # Ambil daftar NIP dosen lain untuk input anggota (kecuali dosen yang sedang login)
        cursor.execute("SELECT NIP, Nama FROM dosen WHERE NIP != %s ORDER BY Nama", (nip_dosen,))
        dosen_list = cursor.fetchall()

        # Ambil daftar NIM mahasiswa
        cursor.execute("SELECT NIM, Nama FROM mahasiswa ORDER BY Nama")
        mahasiswa_list = cursor.fetchall()

        return render_template('dosen/penelitian_dosen.html', 
                               penelitian_list=penelitian_list,
                               dosen_list=dosen_list,
                               mahasiswa_list=mahasiswa_list,
                               current_nip=nip_dosen) 
    
    except Exception as e:
        print(f"Error fetching penelitian dosen data: {e}")
        flash(f"Terjadi error saat mengambil data penelitian: {e}", 'error')
        return redirect(url_for('dashboard_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/dashboard/dosen/penelitian/input', methods=['POST'])
def input_penelitian():
    """
    Memproses input penelitian baru dari dosen, melibatkan 4 tabel (transaksi).
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return jsonify({'success': False, 'message': 'Akses ditolak'}), 403

    conn = None
    cursor = None
    nip_ketua = session['nip_dosen']
    
    try:
        conn = create_connection()
        if not conn:
             return jsonify({'success': False, 'message': 'Koneksi database gagal'}), 500
        
        conn.autocommit = False # Mulai transaksi
        cursor = conn.cursor()
        
        # 1. Ambil Data dari Form
        # Identitas Penelitian (Tabel: penelitian)
        judul_penelitian = request.form['judul_penelitian']
        bidang_ilmu = request.form['bidang_ilmu']
        tahun_pelaksanaan = request.form['tahun_pelaksanaan']
        sumber_pendanaan = request.form['sumber_pendanaan']
        jumlah_dana = request.form['jumlah_dana']
        lama_penelitian = request.form['lama_penelitian']
        status_penelitian = request.form['status_penelitian']

        # Tim Peneliti
        anggota_dosen_nips = request.form.getlist('anggota_dosen[]')
        mahasiswa_nims = request.form.getlist('anggota_mahasiswa[]')

        # Output Penelitian
        jenis_output = request.form.getlist('jenis_output[]')
        keterangan_output = request.form.getlist('keterangan_output[]')

        # Dokumen (Upload Files)
        file_laporan = request.files.get('file_laporan')
        file_artikel = request.files.get('file_artikel')
        file_sertifikat = request.files.get('file_sertifikat')
        file_foto = request.files.get('file_foto')

        # 2. Proses File Upload
        # Untuk kasus produksi, harus ada logika pengecekan ALLOWED_EXTENSIONS dan penamaan unik (e.g., menggunakan UUID)
        
        file_laporan_akhir_path = None
        if file_laporan and allowed_file(file_laporan.filename):
            filename = secure_filename(f"{nip_ketua}_LA_{judul_penelitian[:10]}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_laporan.filename}")
            file_laporan.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file_laporan_akhir_path = filename

        artikel_pdf_path = None
        if file_artikel and allowed_file(file_artikel.filename):
            filename = secure_filename(f"{nip_ketua}_ART_{judul_penelitian[:10]}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_artikel.filename}")
            file_artikel.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            artikel_pdf_path = filename
            
        sertifikat_path = None
        if file_sertifikat and allowed_file(file_sertifikat.filename):
            filename = secure_filename(f"{nip_ketua}_SERT_{judul_penelitian[:10]}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_sertifikat.filename}")
            file_sertifikat.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            sertifikat_path = filename

        foto_kegiatan_path = None
        if file_foto and allowed_file(file_foto.filename):
            filename = secure_filename(f"{nip_ketua}_FOTO_{judul_penelitian[:10]}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_foto.filename}")
            file_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            foto_kegiatan_path = filename


        # 3. INSERT ke tabel 'penelitian'
        sql_penelitian = """
            INSERT INTO penelitian (
                nip_ketua, judul_penelitian, bidang_ilmu, tahun_pelaksanaan, 
                sumber_pendanaan, jumlah_dana, lama_penelitian_bulan, status_penelitian, 
                tanggal_pengajuan, file_laporan_akhir, artikel_pdf, 
                sertifikat_penerimaan, foto_kegiatan, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        now = datetime.now()
        cursor.execute(sql_penelitian, (
            nip_ketua, judul_penelitian, bidang_ilmu, tahun_pelaksanaan, 
            sumber_pendanaan, jumlah_dana, lama_penelitian, status_penelitian, 
            now.date(), file_laporan_akhir_path, artikel_pdf_path, 
            sertifikat_path, foto_kegiatan_path, now, now
        ))
        id_penelitian_baru = cursor.lastrowid # Ambil ID yang baru dibuat


        # 4. INSERT ke tabel 'penelitian_anggota_dosen'
        if anggota_dosen_nips:
            data_anggota_dosen = [(id_penelitian_baru, nip) for nip in anggota_dosen_nips if nip]
            sql_anggota_dosen = "INSERT INTO penelitian_anggota_dosen (id_penelitian, nip_anggota) VALUES (%s, %s)"
            cursor.executemany(sql_anggota_dosen, data_anggota_dosen)


        # 5. INSERT ke tabel 'penelitian_anggota_mahasiswa'
        if mahasiswa_nims:
            data_anggota_mhs = [(id_penelitian_baru, nim) for nim in mahasiswa_nims if nim]
            sql_anggota_mhs = "INSERT INTO penelitian_anggota_mahasiswa (id_penelitian, nim_mahasiswa) VALUES (%s, %s)"
            cursor.executemany(sql_anggota_mhs, data_anggota_mhs)


        # 6. INSERT ke tabel 'penelitian_output'
        if jenis_output and len(jenis_output) == len(keterangan_output):
            data_output = [(id_penelitian_baru, jenis, ket) 
                           for jenis, ket in zip(jenis_output, keterangan_output) if jenis]
            if data_output:
                sql_output = "INSERT INTO penelitian_output (id_penelitian, jenis_output, keterangan) VALUES (%s, %s, %s)"
                cursor.executemany(sql_output, data_output)

        
        conn.commit() # Commit/simpan semua perubahan
        flash('Data penelitian baru berhasil diinput!', 'success')
        return jsonify({'success': True, 'message': 'Data penelitian berhasil disimpan'})

    except Exception as e:
        if conn:
            conn.rollback() # Rollback/batalkan semua perubahan jika terjadi error
        print(f"Error saat input penelitian (transaksi dibatalkan): {e}")
        # Hapus file yang mungkin sudah terupload sebelum error terjadi
        if file_laporan_akhir_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file_laporan_akhir_path)):
             os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file_laporan_akhir_path))
        if artikel_pdf_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], artikel_pdf_path)):
             os.remove(os.path.join(app.config['UPLOAD_FOLDER'], artikel_pdf_path))
        # ... (tambahan untuk file lainnya)

        flash(f'Gagal input penelitian, terjadi error: {e}', 'error')
        return jsonify({'success': False, 'message': f'Gagal menyimpan data: {e}'}), 500
    
    finally:
        if conn:
            conn.autocommit = True
            if cursor:
                cursor.close()
            conn.close()

@app.route('/dashboard/dosen/penelitian/<int:id_penelitian>')
def detail_penelitian(id_penelitian):
    """
    Menampilkan detail lengkap satu penelitian.
    Hanya Ketua/Anggota penelitian yang memiliki akses.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    nip_dosen = session['nip_dosen']
    
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('penelitian_dosen'))
        cursor = conn.cursor(dictionary=True)

        # 1. Ambil Detail Utama Penelitian dan cek hak akses (Ketua atau Anggota)
        sql_detail = """
            SELECT 
                p.*,
                d_ketua.Nama AS nama_ketua,
                (p.nip_ketua = %s OR EXISTS(SELECT 1 FROM penelitian_anggota_dosen pad 
                                           WHERE pad.id_penelitian = p.id_penelitian AND pad.nip_anggota = %s)) AS has_access
            FROM penelitian p
            JOIN dosen d_ketua ON p.nip_ketua = d_ketua.NIP
            WHERE p.id_penelitian = %s
        """
        cursor.execute(sql_detail, (nip_dosen, nip_dosen, id_penelitian))
        detail = cursor.fetchone()

        if not detail or detail['has_access'] == 0:
            flash("Penelitian tidak ditemukan atau Anda tidak memiliki akses.", 'error')
            return redirect(url_for('penelitian_dosen'))
        
        # Tentukan apakah dosen yang login adalah ketua
        is_ketua = (detail['nip_ketua'] == nip_dosen)

        # 2. Ambil Anggota Dosen
        sql_anggota_dosen = """
            SELECT d.NIP, d.Nama
            FROM penelitian_anggota_dosen pad
            JOIN dosen d ON pad.nip_anggota = d.NIP
            WHERE pad.id_penelitian = %s
        """
        cursor.execute(sql_anggota_dosen, (id_penelitian,))
        anggota_dosen_list = cursor.fetchall()
        
        # 3. Ambil Anggota Mahasiswa
        sql_anggota_mhs = """
            SELECT m.NIM, m.Nama, k.nama_kelas
            FROM penelitian_anggota_mahasiswa pam
            JOIN mahasiswa m ON pam.nim_mahasiswa = m.NIM
            LEFT JOIN kelas k ON m.id_kelas = k.id_kelas
            WHERE pam.id_penelitian = %s
        """
        cursor.execute(sql_anggota_mhs, (id_penelitian,))
        anggota_mhs_list = cursor.fetchall()

        # 4. Ambil Output Penelitian
        sql_output = """
            SELECT *
            FROM penelitian_output
            WHERE id_penelitian = %s
        """
        cursor.execute(sql_output, (id_penelitian,))
        output_list = cursor.fetchall()
        
        return render_template('dosen/detail_penelitian.html', 
                               detail=detail,
                               anggota_dosen_list=anggota_dosen_list,
                               anggota_mhs_list=anggota_mhs_list,
                               output_list=output_list,
                               is_ketua=is_ketua) 
    
    except Exception as e:
        print(f"Error fetching detail penelitian: {e}")
        flash(f"Terjadi error saat mengambil detail penelitian: {e}", 'error')
        return redirect(url_for('penelitian_dosen'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# -----------------------------------------------------------------------

# ==================== UPDATE STATUS PENELITIAN ===========================

@app.route('/dashboard/dosen/penelitian/<int:id_penelitian>/update_status', methods=['POST'])
def update_status_penelitian(id_penelitian):
    """
    Endpoint untuk Dosen Ketua memperbarui status penelitian (Selesai/Sedang berjalan).
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return jsonify({'success': False, 'message': 'Akses ditolak'}), 403

    conn = None
    cursor = None
    nip_dosen = session['nip_dosen']
    status_baru = request.form.get('status_baru')
    
    # Validasi Status ENUM
    allowed_statuses = ['Proposal diajukan', 'Diterima', 'Sedang berjalan', 'Selesai']
    if status_baru not in allowed_statuses:
        flash("Status tidak valid.", 'error')
        return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))

    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))
        cursor = conn.cursor()

        # Cek apakah dosen adalah ketua penelitian ini
        cursor.execute("SELECT nip_ketua FROM penelitian WHERE id_penelitian = %s", (id_penelitian,))
        penelitian = cursor.fetchone()
        
        if not penelitian or penelitian[0] != nip_dosen:
            flash("Anda tidak memiliki izin untuk mengubah status penelitian ini.", 'error')
            return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))

        # Lakukan update status
        sql_update = """
            UPDATE penelitian SET status_penelitian = %s, updated_at = %s
            WHERE id_penelitian = %s
        """
        cursor.execute(sql_update, (status_baru, datetime.now(), id_penelitian))
        
        conn.commit()
        flash(f'Status penelitian berhasil diperbarui menjadi "{status_baru}".', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error update status penelitian: {e}")
        flash(f'Gagal memperbarui status: {e}', 'error')
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))

@app.route('/dashboard/dosen/penelitian/<int:id_penelitian>/hapus', methods=['POST'])
def hapus_penelitian(id_penelitian):
    """
    Endpoint untuk Dosen Ketua menghapus data penelitian secara permanen.
    Proses ini melibatkan penghapusan data dari 4 tabel dan menghapus file terunggah.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return jsonify({'success': False, 'message': 'Akses ditolak'}), 403

    conn = None
    cursor = None
    nip_dosen = session['nip_dosen']
    
    try:
        conn = create_connection()
        if not conn:
            flash("Koneksi ke database gagal.", "error")
            return redirect(url_for('penelitian_dosen'))
        
        conn.autocommit = False # Mulai transaksi
        cursor = conn.cursor()

        # 1. Cek apakah dosen adalah ketua penelitian ini
        cursor.execute("SELECT nip_ketua, file_laporan_akhir, artikel_pdf, sertifikat_penerimaan, foto_kegiatan FROM penelitian WHERE id_penelitian = %s", (id_penelitian,))
        penelitian_data = cursor.fetchone() # Menggunakan cursor non-dictionary
        
        if not penelitian_data:
            flash("Penelitian tidak ditemukan.", 'error')
            return redirect(url_for('penelitian_dosen'))
            
        nip_ketua = penelitian_data[0]
        files_to_delete = {
            'file_laporan_akhir': penelitian_data[1],
            'artikel_pdf': penelitian_data[2],
            'sertifikat_penerimaan': penelitian_data[3],
            'foto_kegiatan': penelitian_data[4]
        }

        if nip_ketua != nip_dosen:
            flash("Anda tidak memiliki izin untuk menghapus penelitian ini (Hanya Ketua yang dapat menghapus).", 'error')
            return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))

        # 2. Hapus data dari tabel anak (anggota & output)
        # Hapus Anggota Dosen
        cursor.execute("DELETE FROM penelitian_anggota_dosen WHERE id_penelitian = %s", (id_penelitian,))
        # Hapus Anggota Mahasiswa
        cursor.execute("DELETE FROM penelitian_anggota_mahasiswa WHERE id_penelitian = %s", (id_penelitian,))
        # Hapus Output
        cursor.execute("DELETE FROM penelitian_output WHERE id_penelitian = %s", (id_penelitian,))

        # 3. Hapus data dari tabel utama (penelitian)
        cursor.execute("DELETE FROM penelitian WHERE id_penelitian = %s", (id_penelitian,))
        
        conn.commit() # Commit/simpan semua perubahan database
        
        # 4. Hapus file-file yang terunggah (setelah commit database berhasil)
        deleted_files_count = 0
        upload_folder = app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER_PATH) # Gunakan UPLOAD_FOLDER jika ada, jika tidak gunakan path default
        for key, filename in files_to_delete.items():
            if filename:
                file_path = os.path.join(upload_folder, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_files_count += 1
                    # print(f"File dihapus: {file_path}") # Untuk debugging

        flash(f'Penelitian "{id_penelitian}" berhasil dihapus, termasuk data terkait dan {deleted_files_count} file terunggah.', 'success')
        return redirect(url_for('penelitian_dosen')) # Redirect kembali ke daftar penelitian
        
    except Exception as e:
        if conn:
            conn.rollback() # Rollback/batalkan semua perubahan database jika terjadi error
        print(f"Error saat menghapus penelitian (transaksi dibatalkan): {e}")
        flash(f'Gagal menghapus penelitian: {e}', 'error')
        return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian)) # Kembali ke halaman detail jika gagal
        
    finally:
        if conn:
            conn.autocommit = True
            if cursor:
                cursor.close()
            conn.close()
# =========================================================================
@app.route('/dashboard/dosen/penelitian/<int:id_penelitian>/edit', methods=['GET', 'POST'])
def edit_penelitian(id_penelitian):
    """
    Menangani tampilan form edit (GET) dan pembaruan data (POST) untuk penelitian.
    Ini harus diletakkan sebelum atau di dekat route penelitian lainnya.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        flash("Silakan login kembali.", 'error')
        return redirect(url_for('login'))
        
    # Sementara ini, kita redirect saja kembali ke halaman detail atau daftar
    # Tujuannya hanya agar endpoint 'edit_penelitian' terdaftar di Flask
    
    # KODE LENGKAP UNTUK EDIT AKAN DIBUAT NANTI
    
    if request.method == 'GET':
        # TODO: Logika mengambil detail penelitian yang sudah ada
        # TODO: Logika memverifikasi bahwa dosen yang login adalah ketua
        # return render_template('dosen/edit_penelitian.html', ...) 
        
        # Untuk sementara, redirect ke detail penelitian
        flash("Fitur Edit masih dalam pengembangan.", 'info')
        return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))

    elif request.method == 'POST':
        # TODO: Logika memproses update data
        # flash('Data penelitian berhasil diperbarui!', 'success')
        # return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))
        
        # Untuk sementara, redirect ke detail penelitian
        flash("Fitur Edit belum dapat memproses perubahan data.", 'error')
        return redirect(url_for('detail_penelitian', id_penelitian=id_penelitian))
        
    return redirect(url_for('penelitian_dosen'))

@app.route('/dashboard/dosen/bimbingan')
def dosen_daftar_bimbingan():
    """
    Menampilkan daftar mahasiswa bimbingan untuk dosen yang sedang login.
    Menggunakan NIP yang sudah tersimpan di sesi ('nip_dosen').
    """
    # 1. Autentikasi dan Otorisasi
    if session.get('role') != 'dosen':
        return redirect(url_for('login'))
    
    # *** PERBAIKAN: Ambil NIP dari 'nip_dosen' yang sudah benar ***
    nip_dosen = session.get('nip_dosen') 
    
    if not nip_dosen:
        # Jika nip_dosen belum ada, arahkan kembali ke dashboard utama untuk memicu penyimpanan NIP
        return redirect(url_for('dashboard_dosen')) 

    db = create_connection()
    cursor = db.cursor(dictionary=True)

    mhs_bimbingan = []
    dosen_info = {'Nama': 'N/A'}

    try:
        # 2. Query Data Mahasiswa Bimbingan
        query = """
        SELECT
            b.id_bimbingan,
            m.NIM,
            m.Nama,
            m.id_angkatan AS Angkatan,
            b.jenis_bimbingan AS JenisBimbingan
        FROM bimbingan b
        INNER JOIN mahasiswa m ON b.NIM = m.NIM
        WHERE b.NIP = %s -- NIP yang benar (misalnya 'N02') akan digunakan di sini
        ORDER BY m.Nama ASC;
        """
        cursor.execute(query, (nip_dosen,))
        mhs_bimbingan = cursor.fetchall()

        # 3. Query Data Dosen (untuk judul/info)
        cursor.execute("SELECT Nama FROM dosen WHERE NIP = %s", (nip_dosen,))
        dosen_info = cursor.fetchone()
        
    except Exception as e:
        print(f"Error Dosen Bimbingan: {e}")
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

    return render_template(
        'dosen/daftar-bimbingan.html',
        dosen=dosen_info,
        mhs_bimbingan=mhs_bimbingan,
        user_nip=nip_dosen # Menggunakan user_nip untuk ditampilkan di template
    )

@app.route('/dashboard/dosen/permintaan-bimbingan')
def dosen_permintaan_bimbingan():
    """
    Menampilkan daftar permintaan bimbingan baru/aktif yang harus direspon dosen.
    Ini adalah pusat notifikasi bimbingan.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))
        
    nip_dosen = session.get('nip_dosen')
    conn = None
    cursor = None
    daftar_permintaan = []

    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query untuk mengambil daftar permintaan bimbingan yang ditujukan ke dosen ini
        # (Hanya menggunakan b.NIP = %s, BUKAN pb.id_permintaan = %s)
        sql_query = """
            SELECT 
                pb.id_permintaan,
                pb.topik_bimbingan,
                pb.status_permintaan,
                pb.tanggal_pengajuan,
                pb.tanggal_bimbingan,
                pb.waktu_mulai, -- Ambil ini sebagai timedelta/date
                pb.waktu_selesai, -- Ambil ini sebagai timedelta/date
                m.NIM,
                m.Nama AS nama_mahasiswa,
                b.jenis_bimbingan
            FROM permintaan_bimbingan pb
            JOIN bimbingan b ON pb.id_bimbingan = b.id_bimbingan
            JOIN mahasiswa m ON b.NIM = m.NIM
            WHERE b.NIP = %s
            AND pb.status_permintaan IN ('Menunggu Respon Dosen', 'Jadwal Ditetapkan', 'Membutuhkan Revisi')
            ORDER BY FIELD(pb.status_permintaan, 'Menunggu Respon Dosen', 'Membutuhkan Revisi', 'Jadwal Ditetapkan'), pb.tanggal_pengajuan ASC
        """
        
        # Eksekusi Query: HANYA DENGAN 1 PARAMETER (nip_dosen)
        cursor.execute(sql_query, (nip_dosen,)) 
        daftar_permintaan = cursor.fetchall()
        
        # Catatan: Kita tidak perlu memformat waktu di sini karena 
        # di halaman daftar (permintaan_bimbingan_dosen.html) kita tidak menampilkannya
        # atau jika ditampilkan, error .strftime() dapat dihindari dengan aman di template.
        
        return render_template('dosen/permintaan_bimbingan_dosen.html', 
                               daftar_permintaan=daftar_permintaan) 
        
    except Exception as e:
        # PENTING: Jika terjadi error pada query, pastikan Anda mendapatkan log yang bersih.
        print(f"Error Dosen Permintaan Bimbingan: {e}")
        flash("Terjadi error saat mengambil data permintaan bimbingan.", 'error')
        return redirect(url_for('dashboard_dosen')) 
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ======================================================
# ---- ROUTE: DETAIL PERMINTAAN & FORM RESPON (DOSEN)
# ======================================================

@app.route('/dashboard/dosen/permintaan-bimbingan/detail/<int:id_permintaan>', methods=['GET', 'POST'])
def dosen_detail_dan_respon_bimbingan(id_permintaan):
    """
    Menampilkan detail permintaan dan memproses respon (Terima/Tolak/Revisi).
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))
        
    nip_dosen = session.get('nip_dosen')
    conn = None
    cursor = None
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Query Detail Permintaan dan Cek Kepemilikan (Penting!)
        sql_detail = """
            SELECT 
                pb.*,
                m.NIM,
                m.Nama AS nama_mahasiswa,
                b.jenis_bimbingan
            FROM permintaan_bimbingan pb
            JOIN bimbingan b ON pb.id_bimbingan = b.id_bimbingan
            JOIN mahasiswa m ON b.NIM = m.NIM
            WHERE pb.id_permintaan = %s AND b.NIP = %s
        """
        cursor.execute(sql_detail, (id_permintaan, nip_dosen))
        detail = cursor.fetchone()
        
        if not detail:
            flash("Permintaan bimbingan tidak ditemukan atau bukan bimbingan Anda.", 'error')
            return redirect(url_for('dosen_permintaan_bimbingan'))

        if request.method == 'POST':
            # ==================================
            # PROSES RESPON DOSEN (METODE POST)
            # ==================================
            action = request.form.get('action') # 'terima', 'tolak', atau 'revisi'
            catatan_dosen = request.form.get('catatan_dosen', '').strip()
            
            # Persiapkan data update
            new_status = None
            update_data = {}
            
            if action == 'terima':
                new_status = 'Jadwal Ditetapkan'
                tanggal = request.form.get('tanggal_bimbingan')
                waktu_mulai = request.form.get('waktu_mulai')
                waktu_selesai = request.form.get('waktu_selesai')
                tempat = request.form.get('tempat_bimbingan')
                
                if not all([tanggal, waktu_mulai, waktu_selesai, tempat]):
                    flash("Semua field Jadwal wajib diisi untuk Penerimaan.", 'error')
                    # Tetap tampilkan detail (GET) dengan error
                    return render_template('dosen/detail_bimbingan_dosen.html', detail=detail) 
                
                # Validasi Jam
                if waktu_mulai >= waktu_selesai:
                     flash("Waktu selesai harus setelah waktu mulai.", 'error')
                     return render_template('dosen/detail_bimbingan_dosen.html', detail=detail) 

                update_data = {
                    'tanggal_bimbingan': tanggal,
                    'waktu_mulai': waktu_mulai,
                    'waktu_selesai': waktu_selesai,
                    'tempat_bimbingan': tempat,
                    'catatan_dosen': catatan_dosen,
                }
            
            elif action == 'tolak':
                new_status = 'Ditolak'
                if not catatan_dosen:
                    flash("Alasan penolakan wajib diisi.", 'error')
                    return render_template('dosen/detail_bimbingan_dosen.html', detail=detail)
                update_data = {'catatan_dosen': catatan_dosen}
            
            elif action == 'revisi':
                new_status = 'Membutuhkan Revisi'
                if not catatan_dosen:
                    flash("Instruksi revisi wajib diisi.", 'error')
                    return render_template('dosen/detail_bimbingan_dosen.html', detail=detail)
                update_data = {'catatan_dosen': catatan_dosen}
            
            else:
                flash("Aksi tidak valid.", 'error')
                return redirect(url_for('dosen_permintaan_bimbingan'))

            # Lakukan Update Database (Transaksi)
            update_data['status_permintaan'] = new_status
            update_data['tanggal_update_status'] = datetime.now()
            
            # Buat query update secara dinamis
            set_clauses = [f"{col} = %s" for col in update_data.keys()]
            set_values = list(update_data.values())
            
            sql_update = f"""
                UPDATE permintaan_bimbingan SET {', '.join(set_clauses)}
                WHERE id_permintaan = %s
            """
            set_values.append(id_permintaan)
            
            cursor.execute(sql_update, set_values)
            conn.commit()
            
            flash(f"Permintaan bimbingan berhasil direspon. Status: {new_status}.", 'success')
            return redirect(url_for('dosen_permintaan_bimbingan'))


        # ==================================
        # TAMPILKAN DETAIL (METODE GET)
        # ==================================
        return render_template('dosen/detail_bimbingan_dosen.html', 
                               detail=detail) 
        
    except Exception as e:
        print(f"Error Dosen Respon Bimbingan: {e}")
        if conn: conn.rollback()
        flash("Terjadi error saat memproses respon bimbingan.", 'error')
        return redirect(url_for('dosen_permintaan_bimbingan'))
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ======================================================
# ---- ROUTE: RIWAYAT SEMUA BIMBINGAN (DOSEN)
# ======================================================

@app.route('/dashboard/dosen/riwayat-bimbingan')
def dosen_riwayat_bimbingan():
    """
    Menampilkan semua riwayat permintaan bimbingan, termasuk yang Ditolak/Selesai.
    """
    if session.get('role') != 'dosen' or 'nip_dosen' not in session:
        return redirect(url_for('login'))
        
    nip_dosen = session.get('nip_dosen')
    conn = None
    cursor = None
    riwayat_bimbingan = []

    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query semua riwayat permintaan bimbingan
        sql_query = """
            SELECT 
                pb.id_permintaan,
                pb.topik_bimbingan,
                pb.status_permintaan,
                pb.tanggal_pengajuan,
                pb.tanggal_bimbingan,
                m.NIM,
                m.Nama AS nama_mahasiswa,
                b.jenis_bimbingan
            FROM permintaan_bimbingan pb
            JOIN bimbingan b ON pb.id_bimbingan = b.id_bimbingan
            JOIN mahasiswa m ON b.NIM = m.NIM
            WHERE b.NIP = %s
            ORDER BY pb.tanggal_pengajuan DESC
        """
        cursor.execute(sql_query, (nip_dosen,))
        riwayat_bimbingan = cursor.fetchall()
        
        return render_template('dosen/riwayat_bimbingan_dosen.html', 
                               riwayat=riwayat_bimbingan) 

    except Exception as e:
        print(f"Error Dosen Riwayat Bimbingan: {e}")
        flash("Terjadi error saat mengambil data riwayat bimbingan.", 'error')
        return redirect(url_for('dashboard_dosen')) 
        
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
#================================= KAPRODI SECTION ================================
#==================================================================================
@app.route('/dashboard/kaprodi')
def dashboard_kaprodi():
    if session.get('role') == 'kaprodi':
        return render_template('kaprodi/dashboard_kaprodi.html', user=session['username'])
    return redirect(url_for('login'))



@app.route('/dashboard/kaprodi/requests')
def request_kaprodi():
    """
    Halaman untuk Kaprodi melihat dan mengelola
    permintaan perubahan jadwal (dari tabel 'pertemuan').
    """
    if session.get('role') != 'kaprodi':
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('dashboard_kaprodi'))
        cursor = conn.cursor(dictionary=True)


        base_sql = """
            SELECT 
                p.id_pertemuan AS id_perubahan, -- [DIUBAH]
                p.tanggal_asli,
                p.alasan_perubahan,
                p.tanggal AS tanggal_pengganti, -- [DIUBAH]
                TIME_FORMAT(p.jam_mulai, '%H:%i') AS jam_mulai_pengganti_f, -- [DIUBAH]
                TIME_FORMAT(p.jam_selesai, '%H:%i') AS jam_selesai_pengganti_f, -- [DIUBAH]
                p.ruangan AS ruangan_pengganti, -- [DIUBAH]
                p.status_pertemuan,
                p.catatan_kaprodi,
                p.created_at,
                d.Nama AS nama_dosen,
                mk.nama_matkul,
                k.nama_kelas,
                a.tahun AS angkatan_tahun,
                j.hari AS hari_asli,
                TIME_FORMAT(j.jam_mulai, '%H:%i') AS jam_mulai_asli_f,
                TIME_FORMAT(j.jam_selesai, '%H:%i') AS jam_selai_asli_f,
                j.ruangan AS ruangan_asli
            FROM pertemuan p -- [DIUBAH]
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            JOIN dosen d ON j.nip_dosen = d.NIP
            JOIN matkul mk ON j.kd_mk = mk.kd_mk
            JOIN kelas k ON j.id_kelas = k.id_kelas
            JOIN angkatan a ON j.id_angkatan = a.id_angkatan
        """

        cursor.execute(f"{base_sql} WHERE p.status_pertemuan = 'Diajukan' ORDER BY p.created_at DESC")
        pending_list = cursor.fetchall()
        
        cursor.execute(f"{base_sql} WHERE p.status_pertemuan = 'Disetujui' ORDER BY p.created_at DESC")
        approved_list = cursor.fetchall()
        
        cursor.execute(f"{base_sql} WHERE p.status_pertemuan = 'Ditolak' ORDER BY p.created_at DESC")
        rejected_list = cursor.fetchall()

        return render_template('kaprodi/requests_kaprodi.html', 
                               pending_list=pending_list,
                               approved_list=approved_list,
                               rejected_list=rejected_list)

    except Exception as e:
        print(f"Error fetching kaprodi requests: {e}")
        flash(f"Terjadi error saat mengambil data permintaan: {e}", 'error')
        return redirect(url_for('dashboard_kaprodi'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/dashboard/kaprodi/requests/approve/<int:id_perubahan>', methods=['POST'])
def approve_request(id_perubahan):
    """
    Endpoint untuk MENYETUJUI permintaan (menggunakan id_pertemuan).
    """
    if session.get('role') != 'kaprodi':
        flash("Akses ditolak.", 'error')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('request_kaprodi'))
        cursor = conn.cursor()
        

        cursor.execute("UPDATE pertemuan SET status_pertemuan = 'Disetujui', status_absensi = 'ditutup' WHERE id_pertemuan = %s", (id_perubahan,))
        conn.commit()
        
        flash("Permintaan perubahan jadwal telah disetujui.", 'success')
        
        # TODO: Kirim notifikasi ke Dosen dan Mahasiswa di sini
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error approving request: {e}")
        flash("Terjadi error saat menyetujui permintaan.", 'error')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect(url_for('request_kaprodi'))


@app.route('/dashboard/kaprodi/requests/reject/<int:id_perubahan>', methods=['POST'])
def reject_request(id_perubahan):
    """
    Endpoint untuk MENOLAK permintaan (menggunakan id_pertemuan).
    """
    if session.get('role') != 'kaprodi':
        flash("Akses ditolak.", 'error')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        catatan = request.form.get('catatan_kaprodi')
        if not catatan:
            flash("Alasan penolakan wajib diisi.", 'error')
            return redirect(url_for('request_kaprodi'))

        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('request_kaprodi'))
        cursor = conn.cursor()
        
        
        cursor.execute(
            "UPDATE pertemuan SET status_pertemuan = 'Ditolak', catatan_kaprodi = %s WHERE id_pertemuan = %s", 
            (catatan, id_perubahan)
        )
        conn.commit()
        
        flash("Permintaan perubahan jadwal telah ditolak.", 'success')
        
        # TODO: Kirim notifikasi ke Dosen
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error rejecting request: {e}")
        flash("Terjadi error saat menolak permintaan.", 'error')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect(url_for('request_kaprodi'))

# ======================== MONITORING PENELITIAN KAPRODI ========================

@app.route('/dashboard/kaprodi/penelitian')
def monitoring_penelitian_kaprodi():
    """
    Halaman untuk Kaprodi melihat daftar seluruh penelitian yang diinput dosen.
    """
    if session.get('role') != 'kaprodi':
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('dashboard_kaprodi'))
        cursor = conn.cursor(dictionary=True)

        # Query untuk mengambil semua penelitian
        sql_query = """
            SELECT 
                p.id_penelitian,
                p.judul_penelitian,
                p.tahun_pelaksanaan,
                p.status_penelitian,
                d.Nama AS nama_ketua,
                d.NIP AS nip_ketua
            FROM penelitian p
            JOIN dosen d ON p.nip_ketua = d.NIP
            ORDER BY p.tanggal_pengajuan DESC, p.tahun_pelaksanaan DESC
        """
        cursor.execute(sql_query)
        penelitian_list = cursor.fetchall()

        return render_template('kaprodi/monitoring_penelitian.html', 
                               penelitian_list=penelitian_list)

    except Exception as e:
        print(f"Error fetching all research data for Kaprodi: {e}")
        flash(f"Terjadi error saat mengambil data penelitian: {e}", 'error')
        return redirect(url_for('dashboard_kaprodi'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/dashboard/kaprodi/penelitian/<int:id_penelitian>')
def detail_monitoring_penelitian_kaprodi(id_penelitian):
    """
    Menampilkan detail lengkap satu penelitian (sama seperti detail dosen,
    tapi tanpa perlu cek hak akses ketua).
    """
    if session.get('role') != 'kaprodi':
        return redirect(url_for('login'))
        
    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
             flash("Koneksi ke database gagal.", "error")
             return redirect(url_for('monitoring_penelitian_kaprodi'))
        cursor = conn.cursor(dictionary=True)

        # 1. Ambil Detail Utama Penelitian
        sql_detail = """
            SELECT 
                p.*,
                d_ketua.Nama AS nama_ketua
            FROM penelitian p
            JOIN dosen d_ketua ON p.nip_ketua = d_ketua.NIP
            WHERE p.id_penelitian = %s
        """
        cursor.execute(sql_detail, (id_penelitian,))
        detail = cursor.fetchone()

        if not detail:
            flash("Penelitian tidak ditemukan.", 'error')
            return redirect(url_for('monitoring_penelitian_kaprodi'))

        # 2. Ambil Anggota Dosen
        sql_anggota_dosen = """
            SELECT d.NIP, d.Nama
            FROM penelitian_anggota_dosen pad
            JOIN dosen d ON pad.nip_anggota = d.NIP
            WHERE pad.id_penelitian = %s
        """
        cursor.execute(sql_anggota_dosen, (id_penelitian,))
        anggota_dosen_list = cursor.fetchall()
        
        # 3. Ambil Anggota Mahasiswa
        sql_anggota_mhs = """
            SELECT m.NIM, m.Nama, k.nama_kelas
            FROM penelitian_anggota_mahasiswa pam
            JOIN mahasiswa m ON pam.nim_mahasiswa = m.NIM
            LEFT JOIN kelas k ON m.id_kelas = k.id_kelas
            WHERE pam.id_penelitian = %s
        """
        cursor.execute(sql_anggota_mhs, (id_penelitian,))
        anggota_mhs_list = cursor.fetchall()

        # 4. Ambil Output Penelitian
        sql_output = """
            SELECT *
            FROM penelitian_output
            WHERE id_penelitian = %s
        """
        cursor.execute(sql_output, (id_penelitian,))
        output_list = cursor.fetchall()
        
        return render_template('kaprodi/detail_monitoring_penelitian.html', 
                               detail=detail,
                               anggota_dosen_list=anggota_dosen_list,
                               anggota_mhs_list=anggota_mhs_list,
                               output_list=output_list) 
    
    except Exception as e:
        print(f"Error fetching research detail for Kaprodi: {e}")
        flash(f"Terjadi error saat mengambil detail penelitian: {e}", 'error')
        return redirect(url_for('monitoring_penelitian_kaprodi'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ======================== MONITORING JADWAL KAPRODI ========================

@app.route('/dashboard/kaprodi/jadwal')
def jadwal_kaprodi():
    """
    Halaman untuk Kaprodi melihat daftar seluruh jadwal perkuliahan 
    (mengambil data dari tabel 'jadwal').
    """
    if session.get('role') != 'kaprodi':
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
            flash("Koneksi ke database gagal.", "error")
            return redirect(url_for('dashboard_kaprodi'))
        cursor = conn.cursor(dictionary=True)

        # Query SQL yang diperbarui: 
        # 1. Menambahkan TIME_FORMAT() untuk jam.
        # 2. Menambahkan ORDER BY FIELD() untuk pengurutan hari yang logis.
        sql_query = """
            SELECT 
                j.id_jadwal, 
                m.nama_matkul, 
                d.Nama AS nama_dosen, 
                k.nama_kelas, 
                a.tahun AS angkatan_tahun, -- Diubah dari tahun_angkatan agar sesuai HTML
                j.hari, 
                TIME_FORMAT(j.jam_mulai, '%H:%i') AS jam_mulai_f,  -- Tambahan alias f
                TIME_FORMAT(j.jam_selesai, '%H:%i') AS jam_selesai_f, -- Tambahan alias f
                j.ruangan
            FROM jadwal j
            LEFT JOIN matkul m ON j.kd_mk = m.kd_mk
            LEFT JOIN dosen d ON j.nip_dosen = d.NIP
            LEFT JOIN kelas k ON j.id_kelas = k.id_kelas
            LEFT JOIN angkatan a ON j.id_angkatan = a.id_angkatan
            ORDER BY FIELD(j.hari, 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'), j.jam_mulai
        """
        
        cursor.execute(sql_query)
        jadwal_list = cursor.fetchall()

        return render_template('kaprodi/jadwal_kaprodi.html', 
                               jadwal_list=jadwal_list)

    except Exception as e:
        print(f"Error fetching schedule data for Kaprodi: {e}")
        flash(f"Terjadi error saat mengambil data jadwal: {e}", 'error')
        return redirect(url_for('dashboard_kaprodi'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
# ===========================================================================
#================================== ADMIN SECTION ==================================
#===================================================================================
@app.route('/dashboard/admin')
def dashboard_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
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

        cursor.execute("SELECT COUNT(*) AS total FROM mahasiswa")
        count_mhs = cursor.fetchone()
        if count_mhs:
            counts['mahasiswa'] = count_mhs['total']

        cursor.execute("SELECT COUNT(*) AS total FROM dosen")
        count_dosen = cursor.fetchone()
        if count_dosen:
            counts['dosen'] = count_dosen['total']

        cursor.execute("SELECT COUNT(*) AS total FROM matkul")
        count_mk = cursor.fetchone()
        if count_mk:
            counts['matakuliah'] = count_mk['total']
        
       
        try:
            cursor.execute("SELECT COUNT(*) AS total FROM pertemuan WHERE status_pertemuan = 'Diajukan'")
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

    return render_template('admin/dashboard_admin.html', 
                           user=session['username'], 
                           counts=counts)

@app.route('/dashboard/admin/requests')
def request_admin():
    """
    Halaman untuk Admin melihat dan mengelola
    permintaan perubahan jadwal (dari tabel 'pertemuan').
    """
    # ⚠️ Pengecekan role harus 'admin'
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
            flash("Koneksi ke database gagal.", "error")
            return redirect(url_for('dashboard_admin')) # Sesuaikan dengan URL dashboard admin Anda
        cursor = conn.cursor(dictionary=True)

        base_sql = """
            SELECT 
                p.id_pertemuan AS id_perubahan,
                p.tanggal_asli,
                p.alasan_perubahan,
                p.tanggal AS tanggal_pengganti,
                TIME_FORMAT(p.jam_mulai, '%H:%i') AS jam_mulai_pengganti_f,
                TIME_FORMAT(p.jam_selesai, '%H:%i') AS jam_selesai_pengganti_f,
                p.ruangan AS ruangan_pengganti,
                p.status_pertemuan,
                p.catatan_kaprodi,
                p.created_at,
                d.Nama AS nama_dosen,
                mk.nama_matkul,
                k.nama_kelas,
                a.tahun AS angkatan_tahun,
                j.hari AS hari_asli,
                TIME_FORMAT(j.jam_mulai, '%H:%i') AS jam_mulai_asli_f,
                TIME_FORMAT(j.jam_selesai, '%H:%i') AS jam_selai_asli_f,
                j.ruangan AS ruangan_asli
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            JOIN dosen d ON j.nip_dosen = d.NIP
            JOIN matkul mk ON j.kd_mk = mk.kd_mk
            JOIN kelas k ON j.id_kelas = k.id_kelas
            JOIN angkatan a ON j.id_angkatan = a.id_angkatan
        """

        # Ambil daftar Diajukan
        cursor.execute(f"{base_sql} WHERE p.status_pertemuan = 'Diajukan' ORDER BY p.created_at DESC")
        pending_list = cursor.fetchall()
        
        # Ambil daftar Disetujui
        cursor.execute(f"{base_sql} WHERE p.status_pertemuan = 'Disetujui' ORDER BY p.created_at DESC")
        approved_list = cursor.fetchall()
        
        # Ambil daftar Ditolak
        cursor.execute(f"{base_sql} WHERE p.status_pertemuan = 'Ditolak' ORDER BY p.created_at DESC")
        rejected_list = cursor.fetchall()

        # ⚠️ Render ke template yang sama atau sesuaikan jika ada template khusus admin
        return render_template('admin/requests_admin.html', 
                               pending_list=pending_list,
                               approved_list=approved_list,
                               rejected_list=rejected_list)

    except Exception as e:
        print(f"Error fetching admin requests: {e}")
        flash(f"Terjadi error saat mengambil data permintaan: {e}", 'error')
        return redirect(url_for('dashboard_admin')) # Sesuaikan dengan URL dashboard admin Anda
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/dashboard/admin/requests/approve/<int:id_perubahan>', methods=['POST'])
def approve_request_admin(id_perubahan):
    """
    Endpoint untuk MENYETUJUI permintaan oleh Admin.
    """
    # ⚠️ Pengecekan role harus 'admin'
    if session.get('role') != 'admin':
        flash("Akses ditolak.", 'error')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        conn = create_connection()
        if not conn:
            flash("Koneksi ke database gagal.", "error")
            return redirect(url_for('request_admin')) # Redirect ke halaman Admin
        cursor = conn.cursor()
        
        # Query untuk update status dan status_absensi sama persis
        cursor.execute("UPDATE pertemuan SET status_pertemuan = 'Disetujui', status_absensi = 'ditutup' WHERE id_pertemuan = %s", (id_perubahan,))
        conn.commit()
        
        flash("Permintaan perubahan jadwal telah disetujui.", 'success')
        
        # TODO: Kirim notifikasi ke Dosen dan Mahasiswa di sini
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error approving request by admin: {e}")
        flash("Terjadi error saat menyetujui permintaan.", 'error')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect(url_for('request_admin')) # Redirect ke halaman Admin

@app.route('/dashboard/admin/requests/reject/<int:id_perubahan>', methods=['POST'])
def reject_request_admin(id_perubahan):
    """
    Endpoint untuk MENOLAK permintaan oleh Admin.
    """
    # ⚠️ Pengecekan role harus 'admin'
    if session.get('role') != 'admin':
        flash("Akses ditolak.", 'error')
        return redirect(url_for('login'))

    conn = None
    cursor = None
    try:
        # Mengambil catatan dari form POST
        catatan = request.form.get('catatan_kaprodi') 
        if not catatan:
            flash("Alasan penolakan wajib diisi.", 'error')
            return redirect(url_for('request_admin')) # Redirect ke halaman Admin

        conn = create_connection()
        if not conn:
            flash("Koneksi ke database gagal.", "error")
            return redirect(url_for('request_admin')) # Redirect ke halaman Admin
        cursor = conn.cursor()
        
        # Query untuk update status dan catatan sama persis
        cursor.execute(
            "UPDATE pertemuan SET status_pertemuan = 'Ditolak', catatan_kaprodi = %s WHERE id_pertemuan = %s", 
            (catatan, id_perubahan)
        )
        conn.commit()
        
        flash("Permintaan perubahan jadwal telah ditolak.", 'success')
        
        # TODO: Kirim notifikasi ke Dosen
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error rejecting request by admin: {e}")
        flash("Terjadi error saat menolak permintaan.", 'error')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect(url_for('request_admin')) # Redirect ke halaman Admin


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

#Kelola Mahasiswa
@app.route('/dashboard/admin/kelola-data/mahasiswa')
def admin_kelola_mahasiswa():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            
            sql_query = """
            SELECT 
                m.NIM, 
                m.Nama, 
                m.id_kelas, 
                m.id_angkatan,
                m.foto,              -- DATA FOTO BARU
                k.nama_kelas, 
                a.tahun 
            FROM mahasiswa m
            LEFT JOIN kelas k ON m.id_kelas = k.id_kelas
            LEFT JOIN angkatan a ON m.id_angkatan = a.id_angkatan;
            """
            cursor.execute(sql_query) 
            
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


# ----------------------------------------------------------------------
# # KELOLA DATA MAHASISWA (HAPUS)
# ----------------------------------------------------------------------
@app.route('/dashboard/admin/kelola-data/mahasiswa/hapus/<string:nim>')
def hapus_mahasiswa(nim):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Ambil nama file foto yang terkait
        cursor.execute("SELECT foto FROM mahasiswa WHERE NIM = %s", (nim,))
        result = cursor.fetchone()
        foto_to_delete = result[0] if result and result[0] else None 
        
        # 2. Hapus file foto dari server (jika ada)
        if foto_to_delete:
            filepath = os.path.join(UPLOAD_FOLDER, foto_to_delete)
            if os.path.exists(filepath):
                os.remove(filepath)
                
        # 3. Hapus data dari database
        cursor.execute("DELETE FROM mahasiswa WHERE NIM = %s", (nim,)) 
        conn.commit()
        
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_kelola_mahasiswa')) 


# ----------------------------------------------------------------------
# # KELOLA DATA MAHASISWA (TAMBAH)
# ----------------------------------------------------------------------
@app.route('/dashboard/admin/kelola-data/mahasiswa/tambah', methods=['GET', 'POST'])
def tambah_mahasiswa():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id_kelas, nama_kelas FROM kelas")
        kelas_list = cursor.fetchall()
        cursor.execute("SELECT id_angkatan, tahun FROM angkatan")
        angkatan_list = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching dropdown data: {e}")
        kelas_list = []
        angkatan_list = []

    if request.method == 'POST':
        nim_baru = request.form['nim']
        nama_baru = request.form['nama']
        id_kelas_baru = request.form['id_kelas']
        id_angkatan_baru = request.form['id_angkatan']
        
        foto_filename = None
        
        # 1. Menangani File Upload
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                foto_filename = f"{nim_baru}.{ext}" # Penamaan file menggunakan NIM
                filepath = os.path.join(UPLOAD_FOLDER, foto_filename)
                
                file.save(filepath)
            
        try:
            # 2. Modifikasi Query INSERT untuk menyertakan kolom foto
            sql_insert = "INSERT INTO mahasiswa (NIM, Nama, id_kelas, id_angkatan, foto) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql_insert, 
                           (nim_baru, nama_baru, id_kelas_baru, id_angkatan_baru, foto_filename))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
            # Rollback foto jika insert gagal
            if foto_filename and os.path.exists(os.path.join(UPLOAD_FOLDER, foto_filename)):
                os.remove(os.path.join(UPLOAD_FOLDER, foto_filename))
        finally:
            cursor.close()
            conn.close()
            return redirect(url_for('admin_kelola_mahasiswa')) 
            
    cursor.close()
    conn.close()
    return render_template('admin/tambah_mahasiswa_form.html', 
                           user=session['username'],
                           kelas_list=kelas_list, 
                           angkatan_list=angkatan_list 
                         )


# ----------------------------------------------------------------------
# # KELOLA DATA MAHASISWA (EDIT)
# ----------------------------------------------------------------------
@app.route('/dashboard/admin/kelola-data/mahasiswa/edit/<string:nim>', methods=['GET', 'POST'])
def edit_mahasiswa(nim):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    # Ambil daftar kelas dan angkatan untuk dropdown
    try:
        cursor.execute("SELECT id_kelas, nama_kelas FROM kelas")
        kelas_list = cursor.fetchall()
        cursor.execute("SELECT id_angkatan, tahun FROM angkatan")
        angkatan_list = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching dropdown data for edit: {e}")
        kelas_list = []
        angkatan_list = []


    if request.method == 'POST':
        nama_baru = request.form['nama']
        id_kelas_baru = request.form['id_kelas']
        id_angkatan_baru = request.form['id_angkatan']
        
        # 1. Ambil data foto lama
        cursor.execute("SELECT foto FROM mahasiswa WHERE NIM = %s", (nim,))
        mahasiswa_lama = cursor.fetchone()
        foto_lama = mahasiswa_lama['foto'] if mahasiswa_lama else None
        foto_filename = foto_lama # Default: pertahankan foto lama

        # 2. Menangani File Upload Baru
        if 'foto' in request.files:
            file = request.files['foto']
            if file.filename != '' and allowed_file(file.filename):
                
                # Hapus foto lama di server jika ada foto baru diupload
                if foto_lama and os.path.exists(os.path.join(UPLOAD_FOLDER, foto_lama)):
                    try:
                        os.remove(os.path.join(UPLOAD_FOLDER, foto_lama))
                    except Exception as e:
                        print(f"Error deleting old photo: {e}")

                # Simpan foto baru
                ext = file.filename.rsplit('.', 1)[1].lower()
                foto_filename = f"{nim}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, foto_filename)
                file.save(filepath)
                
        try:
            # 3. Modifikasi Query UPDATE untuk menyertakan kolom foto
            sql_update = "UPDATE mahasiswa SET Nama = %s, id_kelas = %s, id_angkatan = %s, foto = %s WHERE NIM = %s"
            cursor.execute(sql_update,
                           (nama_baru, id_kelas_baru, id_angkatan_baru, foto_filename, nim))
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_mahasiswa'))
        
    # BAGIAN GET (Menampilkan Form Edit)
    try:
        cursor.execute("SELECT * FROM mahasiswa WHERE NIM = %s", (nim,))
        mahasiswa_data = cursor.fetchone() 
        
        if not mahasiswa_data:
            cursor.close()
            conn.close()
            return "Data Mahasiswa tidak ditemukan.", 404
            
        return render_template('admin/edit_mahasiswa_form.html', 
                               user=session['username'], 
                               mahasiswa=mahasiswa_data,
                               kelas_list=kelas_list,
                               angkatan_list=angkatan_list) 
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        # Pastikan koneksi ditutup jika bukan request POST
        if not conn.close:
            cursor.close()
            conn.close()

# KELOLA MATAKULIAH
@app.route('/dashboard/admin/kelola-data/matakuliah')
def admin_kelola_matakuliah():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
   
            cursor.execute("SELECT * FROM matkul") 
            
            daftar_matakuliah = cursor.fetchall()
            
            cursor.close()
            conn.close()

            return render_template('admin/kelola_matakuliah_list.html', 
                                    user=session['username'], 
                                    daftar_matakuliah=daftar_matakuliah) 
        
        except Exception as e:
            print(f"Error reading matakuliah database: {e}")
            return "Terjadi error saat mengambil data."    
    return redirect(url_for('login'))

@app.route('/dashboard/admin/kelola-data/matakuliah/hapus/<string:kodemk>')
def hapus_matakuliah(kodemk):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
 
        cursor.execute("DELETE FROM matkul WHERE kd_mk = %s", (kodemk,)) 
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_kelola_matakuliah')) 

@app.route('/dashboard/admin/kelola-data/matakuliah/tambah', methods=['GET', 'POST'])
def tambah_matakuliah():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':

        kodemk_baru = request.form['kd_mk']
        nama_matkul_baru = request.form['nama_matkul']
        sks_baru = request.form['sks']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            

            cursor.execute("INSERT INTO matkul (kd_mk, nama_matkul, sks) VALUES (%s, %s, %s)", 
                           (kodemk_baru, nama_matkul_baru, sks_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_matakuliah')) 

 
    return render_template('admin/tambah_matakuliah_form.html', user=session['username'])

@app.route('/dashboard/admin/kelola-data/matakuliah/edit/<string:kodemk>', methods=['GET', 'POST'])
def edit_matakuliah(kodemk): 
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':

        nama_matkul_baru = request.form['nama_matkul']
        sks_baru = request.form['sks']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            

            cursor.execute("UPDATE matkul SET nama_matkul = %s, sks = %s WHERE kd_mk = %s",
                           (nama_matkul_baru, sks_baru, kodemk))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
            
            return redirect(url_for('admin_kelola_matakuliah'))


    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 
        

        cursor.execute("SELECT * FROM matkul WHERE kd_mk = %s", (kodemk,))
        matakuliah_data = cursor.fetchone() 
        
        if not matakuliah_data:
            return "Data Mata Kuliah tidak ditemukan.", 404

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

            cursor.execute("SELECT * FROM kelas") 
            
            daftar_kelas = cursor.fetchall()
            
            cursor.close()
            conn.close()

            return render_template('admin/kelola_kelas_list.html', 
                                    user=session['username'], 
                                    daftar_kelas=daftar_kelas) 
        
        except Exception as e:
            print(f"Error reading matakuliah database: {e}")
            return "Terjadi error saat mengambil data."    
    return redirect(url_for('login'))
@app.route('/dashboard/admin/kelola-data/kelas/hapus/<int:id_kelas>')
def hapus_kelas(id_kelas): 
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
  
        cursor.execute("DELETE FROM kelas WHERE id_kelas = %s", (id_kelas,)) 
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_kelola_kelas')) 

@app.route('/dashboard/admin/kelola-data/kelas/tambah', methods=['GET', 'POST'])
def tambah_kelas():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        id_kelas_baru = request.form['id_kelas']
        nama_kelas_baru = request.form['nama_kelas']

        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            cursor.execute("INSERT INTO kelas (id_kelas, nama_kelas) VALUES (%s, %s)", 
                           (id_kelas_baru, nama_kelas_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_kelas')) 


    return render_template('admin/tambah_kelas_form.html', user=session['username'])

@app.route('/dashboard/admin/kelola-data/kelas/edit/<int:id_kelas>', methods=['GET', 'POST'])
def edit_kelas(id_kelas): 
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama_kelas_baru = request.form['nama_kelas']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()

            # --- CORRECTED LINE BELOW ---
            # 1. Removed the extra comma after the first %s
            # 2. Included both nama_kelas_baru and id_kelas in the tuple
            cursor.execute("UPDATE kelas SET nama_kelas = %s WHERE id_kelas = %s",
                           (nama_kelas_baru, id_kelas))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
            # Consider adding a flash message here for the user
        finally:
            cursor.close()
            conn.close()
            
            return redirect(url_for('admin_kelola_kelas'))
# ... rest of the function (GET method) is fine


    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True) 
        
        cursor.execute("SELECT * FROM kelas WHERE id_kelas = %s", (id_kelas,))
        kelas_data = cursor.fetchone() 
        
        if not kelas_data:
            return "Data kelas tidak ditemukan.", 404
            
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
 
#Kaprodi
@app.route('/dashboard/admin/kelola-data/kaprodi')
def admin_kelola_kaprodi():
    if session.get('role') == 'admin':
        try:
            conn = create_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM kaprodi") 
            daftar_kaprodi = cursor.fetchall()
        except Exception as e:
            print(f"Error reading angkatan database: {e}")
            return "Terjadi error saat mengambil data."
        finally:
            cursor.close()
            conn.close()
        return render_template('admin/kelola_kaprodi_list.html', 
                               user=session['username'], 
                               daftar_kaprodi=daftar_kaprodi)
    return redirect(url_for('login'))

@app.route('/dashboard/admin/kelola-data/kaprodi/tambah', methods=['GET', 'POST'])
def tambah_kaprodi():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nip_baru = request.form['NIP']
        nama_baru = request.form['Nama']
        
        try:
            conn = create_connection()
            cursor = conn.cursor()
            
            cursor.execute("INSERT INTO kaprodi (NIP, Nama) VALUES (%s, %s)", 
                           (nip_baru, nama_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_kelola_kaprodi')) 

    # Tampilkan form tambah matakuliah
    return render_template('admin/tambah_kaprodi_form.html', user=session['username'])

@app.route('/dashboard/admin/kelola-data/kaprodi/hapus/<string:NIP>')
def hapus_kaprodi(NIP):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM kaprodi WHERE NIP = %s", (NIP,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting data: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_kelola_kaprodi'))

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

# ======================================================
# ---- ROUTE: Tambah Akun Admin
# ======================================================
@app.route('/dashboard/admin/kelola-akun/admin/tambah', methods=['GET', 'POST'])
def tambah_akun_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor() # Gunakan cursor standar untuk operasi INSERT/GET ID

    if request.method == 'POST':
        nama_admin = request.form['nama_admin'] # Nama dari tabel admin
        username = request.form['username']
        password = request.form['password']
        
        try:
            # 1. Masukkan data ke tabel 'admin' untuk mendapatkan ID_Admin baru
            # Asumsi: kolom Nama di tabel admin adalah nama lengkap admin
            cursor.execute("INSERT INTO admin (Nama) VALUES (%s)", (nama_admin,))
            
            # Ambil ID_Admin yang baru saja dibuat (AI: Auto Increment)
            # Metode ini tergantung pada driver database (misal, MySQL: LAST_INSERT_ID())
            id_admin_baru = cursor.lastrowid 

            # Jika berhasil mendapatkan ID_Admin
            if id_admin_baru:
                # 2. Masukkan data ke tabel 'akun' dengan id_admin yang terkait
                # Pastikan nim_mahasiswa, nip_dosen, nip_kaprodi diset NULL/kosong
                # Atau, hanya isi kolom yang relevan: Username, Password, id_admin
                cursor.execute("""
                    INSERT INTO akun (Username, Password, id_admin) 
                    VALUES (%s, %s, %s)
                """, (username, password, id_admin_baru))
                
                conn.commit()
                # Redirect ke daftar akun admin setelah berhasil
                return redirect(url_for('admin_akun_admin_list')) 
            
        except Exception as e:
            print(f"Error inserting Admin account: {e}")
            conn.rollback()
            # Anda mungkin ingin menambahkan pesan error flash di sini
            
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_admin_list')) # Redirect ke halaman list dengan error/sukses
    
    # Bagian GET request: Tampilkan form tambah
    try:
        # Tidak ada data tambahan yang perlu diambil, hanya tampilkan form
        return render_template('admin/tambah_akun_admin_form.html', 
                                user=session['username'])
    except Exception as e:
        print(f"Error rendering form: {e}")
        return "Terjadi error saat menampilkan form."
    

# ======================================================
# ---- ROUTE 3: Daftar Akun Admin (READ)
# ======================================================
@app.route('/dashboard/admin/kelola-akun/admin')
def admin_akun_admin_list():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        # JOIN antara tabel akun dan admin untuk menampilkan Nama lengkap
        cursor.execute("""
            SELECT 
                a.Username, 
                a.Password, -- *Sebaiknya jangan tampilkan password asli di sistem real*
                d.Nama, 
                d.ID_Admin
            FROM akun a
            INNER JOIN admin d ON a.id_admin = d.ID_Admin
            WHERE a.id_admin IS NOT NULL
            ORDER BY d.Nama ASC
        """)
        daftar_akun = cursor.fetchall()
        
        return render_template(
            'admin/kelola_akun_admin_list.html', 
            user=session['username'], 
            daftar_akun=daftar_akun
        )
    except Exception as e:
        print(f"Error reading admin account data: {e}")
        return "Terjadi error saat mengambil data."
    finally:
        cursor.close()
        conn.close()

# ======================================================
# ---- ROUTE 4: Edit Akun Admin (UPDATE)
# ======================================================
@app.route('/dashboard/admin/kelola-akun/admin/edit/<string:username>', methods=['GET', 'POST'])
def edit_akun_admin(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Ambil data dari form POST
        new_password = request.form['password'] 
        new_nama = request.form['nama_admin']
        id_admin = request.form['id_admin'] # Hidden input field dari form
        
        try:
            # 1. Update tabel akun (Password)
            cursor.execute("UPDATE akun SET Password = %s WHERE Username = %s",
                           (new_password, username))
            
            # 2. Update tabel admin (Nama)
            cursor.execute("UPDATE admin SET Nama = %s WHERE ID_Admin = %s",
                           (new_nama, id_admin))
            
            conn.commit()
        except Exception as e:
            print(f"Error updating Admin account: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin_akun_admin_list'))
    
    # GET request: Tampilkan form edit
    try:
        # Ambil data akun dan detail admin berdasarkan Username
        cursor.execute("""
            SELECT 
                a.Username, a.Password, d.Nama, d.ID_Admin
            FROM akun a
            INNER JOIN admin d ON a.id_admin = d.ID_Admin
            WHERE a.Username = %s
        """, (username,))
        akun_data = cursor.fetchone()
        
    except Exception as e:
        print(f"Error fetching data for edit: {e}")
        return "Error mengambil data."
    finally:
        cursor.close()
        conn.close()
        
    if not akun_data:
        return "Akun Admin tidak ditemukan.", 404
        
    return render_template('admin/edit_akun_admin_form.html', 
                           user=session['username'], 
                           akun=akun_data)

# ======================================================
# ---- ROUTE 5: Hapus Akun Admin (DELETE)
# ======================================================
@app.route('/dashboard/admin/kelola-akun/admin/hapus/<string:username>')
def hapus_akun_admin(username):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Ambil ID_Admin terkait sebelum dihapus
        cursor.execute("SELECT id_admin FROM akun WHERE Username = %s", (username,))
        result = cursor.fetchone()
        if not result:
             return "Akun tidak ditemukan.", 404
        id_admin_to_delete = result[0]
        
        # 2. Hapus dari tabel akun (karena akun memiliki FK ke admin)
        cursor.execute("DELETE FROM akun WHERE Username = %s", (username,))
        
        # 3. Hapus dari tabel admin
        cursor.execute("DELETE FROM admin WHERE ID_Admin = %s", (id_admin_to_delete,))
        
        conn.commit()
    except Exception as e:
        print(f"Error deleting Admin account: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('admin_akun_admin_list'))
#============================ PAGE BIMBINGAN ==================================

@app.route('/dashboard/admin/kelola-bimbingan')
def admin_kelola_bimbingan():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = create_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # Query paling aman & kompatibel
        query = """
        SELECT 
            d.NIP,
            d.Nama,
            d.ProgramStudi,
            COALESCE(COUNT(b.id_bimbingan), 0) AS TotalMhsBimbingan
        FROM dosen d
        LEFT JOIN bimbingan b ON d.NIP = b.NIP
        GROUP BY d.NIP, d.Nama, d.ProgramStudi
        ORDER BY d.Nama ASC;
        """
        cursor.execute(query)
        dosen_data = cursor.fetchall()

    except Exception as e:
        print("Error:", e)
        dosen_data = []
    finally:
        cursor.close()
        db.close()

    return render_template(
        'admin/kelola-bimbingan.html',
        user=session.get('username'),
        dosens=dosen_data
    )

# ======================================================
# ---- ROUTE 2: Detail mahasiswa bimbingan per dosen (SUDAH DIPERBAIKI)
# ======================================================
@app.route('/dashboard/admin/kelola-bimbingan/<nip>')
def admin_kelola_mahasiswa_bimbingan(nip):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = create_connection()
    cursor = db.cursor(dictionary=True)

    try:
        # Data dosen
        cursor.execute("SELECT NIP, Nama FROM dosen WHERE NIP = %s", (nip,))
        dosen = cursor.fetchone()
        if not dosen:
            return "Dosen tidak ditemukan", 404

        # Mahasiswa yang dibimbing dosen ini
        cursor.execute("""
            SELECT
                b.id_bimbingan,
                m.NIM,
                m.Nama,
                m.id_angkatan AS Angkatan,
                b.jenis_bimbingan AS JenisBimbingan
            FROM bimbingan b
            INNER JOIN mahasiswa m ON b.NIM = m.NIM
            WHERE b.NIP = %s
            ORDER BY m.Nama;
        """, (nip,))
        mhs_bimbingan = cursor.fetchall()

        # Mahasiswa yang BELUM dibimbing oleh DOSEN MANAPUN (PERBAIKAN ADA DI SINI)
        # Mahasiswa yang NIM-nya sudah ada di tabel bimbingan tidak akan dimasukkan ke daftar ini.
        cursor.execute("""
            SELECT
                NIM,
                Nama,
                id_angkatan
            FROM mahasiswa
            WHERE NIM NOT IN (
                SELECT NIM FROM bimbingan -- **INI YANG DIPERBAIKI**
            )
            ORDER BY Nama;
        """)
        # Karena query sudah tidak menggunakan %s, tuple (nip,) dihilangkan.
        mahasiswa_tersedia = cursor.fetchall()

    except Exception as e:
        print("DB Error:", e)
        return "Kesalahan database", 500
    finally:
        cursor.close()
        db.close()

    return render_template(
        'admin/kelola-mahasiswa-bimbingan.html',
        dosen=dosen,
        mhs_bimbingan=mhs_bimbingan,
        mahasiswa_tersedia=mahasiswa_tersedia
    )
# ======================================================
# ---- API CREATE BIMBINGAN
# ======================================================
@app.route('/api/bimbingan/add', methods=['POST'])
def add_bimbingan():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json
    nip = data.get('nip')
    nim = data.get('nim')
    jenis = data.get('jenis')

    if not all([nip, nim, jenis]):
        return jsonify({'success': False, 'message': 'Data tidak lengkap'}), 400

    db = create_connection()
    cursor = db.cursor()

    try:
        # Cek duplikasi
        cursor.execute("""
            SELECT COUNT(*) 
            FROM bimbingan 
            WHERE NIP = %s AND NIM = %s
        """, (nip, nim))
        
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Mahasiswa sudah dibimbing'}), 409

        # Insert
        cursor.execute("""
            INSERT INTO bimbingan (NIP, NIM, jenis_bimbingan)
            VALUES (%s, %s, %s)
        """, (nip, nim, jenis))
        
        db.commit()

        return jsonify({'success': True, 'id_bimbingan': cursor.lastrowid}), 200

    except Exception as e:
        print("Insert Error:", e)
        db.rollback()
        return jsonify({'success': False, 'message': 'Database error'}), 500
    finally:
        cursor.close()
        db.close()


# ======================================================
# ---- API DELETE BIMBINGAN
# ======================================================
@app.route('/api/bimbingan/delete/<int:id_bimbingan>', methods=['DELETE'])
def delete_bimbingan(id_bimbingan):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    db = create_connection()
    cursor = db.cursor()

    try:
        # --- LANGKAH PENTING: Hapus semua data anak (child) terlebih dahulu ---
        # Data permintaan_bimbingan memiliki FOREIGN KEY ke bimbingan.
        # Jika data anak tidak dihapus, data induk tidak bisa dihapus.
        print(f"Menghapus permintaan bimbingan untuk id_bimbingan: {id_bimbingan}")
        cursor.execute("DELETE FROM permintaan_bimbingan WHERE id_bimbingan = %s", (id_bimbingan,))
        
        # --- LANGKAH 2: Hapus data induk (parent) ---
        # Setelah semua referensi di tabel anak dihapus, operasi ini akan berhasil.
        print(f"Menghapus data bimbingan untuk id_bimbingan: {id_bimbingan}")
        cursor.execute("DELETE FROM bimbingan WHERE id_bimbingan = %s", (id_bimbingan,))
        
        # Commit transaksi
        db.commit()

        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Berhasil dihapus'}), 200
        else:
            # Mengembalikan status 404 jika ID bimbingan tidak ditemukan
            return jsonify({'success': False, 'message': 'ID tidak ditemukan'}), 404

    except Exception as e:
        # Cetak error yang lebih informatif ke console server
        print(f"Delete Error (id={id_bimbingan}): {e}")
        db.rollback()
        # Mengembalikan status 500 jika terjadi kesalahan database lainnya
        return jsonify({'success': False, 'message': 'Database error'}), 500
    finally:
        cursor.close()
        db.close()

#========================== PAGE KELOLA JADWAL ==========================================
@app.route('/dashboard/admin/kelola-jadwal')
def admin_kelola_jadwal():
    if session.get('role') == 'admin':
        return render_template('admin/kelola-jadwal.html', user=session['username'])
    return redirect(url_for('login'))

#JADWAL MATAKULIAH
@app.route('/dashboard/admin/kelola-jadwal/matakuliah')
def admin_jadwal_matakuliah_list():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                j.id_jadwal, 
                m.nama_matkul, 
                d.Nama AS nama_dosen, 
                k.nama_kelas, 
                a.tahun AS tahun_angkatan,
                j.hari, 
                j.jam_mulai, 
                j.jam_selesai, 
                j.ruangan
            FROM jadwal j
            LEFT JOIN matkul m ON j.kd_mk = m.kd_mk
            LEFT JOIN dosen d ON j.nip_dosen = d.NIP
            LEFT JOIN kelas k ON j.id_kelas = k.id_kelas
            LEFT JOIN angkatan a ON j.id_angkatan = a.id_angkatan
        """)
        daftar_jadwal = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching schedule list: {e}")
        daftar_jadwal = []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
            
    return render_template('admin/kelola_jadwal_matakuliah_list.html', 
                           user=session['username'], 
                           daftar_jadwal=daftar_jadwal)

@app.route('/dashboard/admin/kelola-jadwal/matakuliah/tambah', methods=['GET', 'POST'])
def tambah_jadwal_matakuliah():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        kd_mk = request.form['kd_mk']
        nip_dosen = request.form['nip_dosen']
        id_kelas = request.form['id_kelas']
        id_angkatan = request.form['id_angkatan']
        ruangan = request.form['ruangan']
        hari = request.form['hari']
        jam_mulai = request.form['jam_mulai']
        jam_selesai = request.form['jam_selesai']
        
        try:
            cursor.execute("""
                INSERT INTO jadwal (kd_mk, nip_dosen, id_kelas, id_angkatan, ruangan, hari, jam_mulai, jam_selesai) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (kd_mk, nip_dosen, id_kelas, id_angkatan, ruangan, hari, jam_mulai, jam_selesai))
            conn.commit()
        except Exception as e:
            print(f"Error inserting schedule: {e}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_jadwal_matakuliah_list'))

    try:
        cursor.execute("SELECT kd_mk, nama_matkul FROM matkul")
        daftar_matkul = cursor.fetchall()
        
        cursor.execute("SELECT NIP, Nama FROM dosen")
        daftar_dosen = cursor.fetchall()
        
        cursor.execute("SELECT id_kelas, nama_kelas FROM kelas")
        daftar_kelas = cursor.fetchall()
        
        cursor.execute("SELECT id_angkatan, tahun FROM angkatan")
        daftar_angkatan = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching lists for schedule form: {e}")
        daftar_matkul, daftar_dosen, daftar_kelas, daftar_angkatan = [], [], [], []
    finally:
        cursor.close()
        conn.close()

    return render_template('admin/tambah_jadwal_matakuliah_form.html', 
                           user=session['username'],
                           daftar_matkul=daftar_matkul,
                           daftar_dosen=daftar_dosen,
                           daftar_kelas=daftar_kelas,
                           daftar_angkatan=daftar_angkatan)

@app.route('/dashboard/admin/kelola-jadwal/matakuliah/edit/<int:id_jadwal>', methods=['GET', 'POST'])
def edit_jadwal_matakuliah(id_jadwal):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        kd_mk = request.form['kd_mk']
        nip_dosen = request.form['nip_dosen']
        id_kelas = request.form['id_kelas']
        id_angkatan = request.form['id_angkatan']
        ruangan = request.form['ruangan']
        hari = request.form['hari']
        jam_mulai = request.form['jam_mulai']
        jam_selesai = request.form['jam_selesai']
        
        try:
            cursor.execute("""
                UPDATE jadwal SET 
                    kd_mk = %s, 
                    nip_dosen = %s, 
                    id_kelas = %s, 
                    id_angkatan = %s, 
                    ruangan = %s, 
                    hari = %s, 
                    jam_mulai = %s, 
                    jam_selesai = %s
                WHERE id_jadwal = %s
            """, (kd_mk, nip_dosen, id_kelas, id_angkatan, ruangan, hari, jam_mulai, jam_selesai, id_jadwal))
            conn.commit()
        except Exception as e:
            print(f"Error updating schedule: {e}")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('admin_jadwal_matakuliah_list'))

    try:
        cursor.execute("SELECT * FROM jadwal WHERE id_jadwal = %s", (id_jadwal,))
        jadwal_data = cursor.fetchone()
        

        cursor.execute("SELECT kd_mk, nama_matkul FROM matkul")
        daftar_matkul = cursor.fetchall()
        
        cursor.execute("SELECT NIP, Nama FROM dosen")
        daftar_dosen = cursor.fetchall()
        
        cursor.execute("SELECT id_kelas, nama_kelas FROM kelas")
        daftar_kelas = cursor.fetchall()
        
        cursor.execute("SELECT id_angkatan, tahun FROM angkatan")
        daftar_angkatan = cursor.fetchall()
        
    except Exception as e:
        print(f"Error fetching data for schedule edit: {e}")
        return "Error mengambil data"
    finally:
        cursor.close()
        conn.close()
        
    if not jadwal_data:
        return "Jadwal tidak ditemukan", 404

    return render_template('admin/edit_jadwal_matakuliah_form.html', 
                           user=session['username'],
                           jadwal=jadwal_data, 
                           daftar_matkul=daftar_matkul,
                           daftar_dosen=daftar_dosen,
                           daftar_kelas=daftar_kelas,
                           daftar_angkatan=daftar_angkatan)

@app.route('/dashboard/admin/kelola-jadwal/matakuliah/hapus/<int:id_jadwal>')
def hapus_jadwal_matakuliah(id_jadwal):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM jadwal WHERE id_jadwal = %s", (id_jadwal,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting schedule: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            
    return redirect(url_for('admin_jadwal_matakuliah_list'))
#JADWAL BIMBINGAN

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)