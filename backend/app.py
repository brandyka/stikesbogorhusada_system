from flask import Flask, render_template, request, redirect, session, url_for,send_from_directory, flash
from db_conn import create_connection
import os
from datetime import datetime, date
from pyngrok import ngrok
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
        
    conn = None
    cursor = None
    try:
        username = session.get('username')
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        sql_query = """
            SELECT 
                m.NIM, m.Nama, 
                m.id_kelas, m.id_angkatan,  -- Ambil ID untuk session
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
        

        sql_get_pertemuan_hari_ini = """
            SELECT 
                p.id_jadwal, p.id_pertemuan, p.materi, p.pertemuan_ke,
                am.status_kehadiran AS status_kehadiran_saya
            FROM pertemuan p
            JOIN jadwal j ON p.id_jadwal = j.id_jadwal
            LEFT JOIN absensi_mahasiswa am ON p.id_pertemuan = am.id_pertemuan
                                           AND am.nim_mahasiswa = %s
            WHERE j.id_kelas = %s AND j.id_angkatan = %s
              AND p.status_absensi = 'dibuka'
              AND p.tanggal = %s 
              AND p.status_pertemuan IN ('Reguler', 'Disetujui')
        """
    
        cursor.execute(sql_get_pertemuan_hari_ini, (nim_mhs, id_kelas_mhs, id_angkatan_mhs, today_date))
        pertemuan_hari_ini_list = cursor.fetchall()
        
  
        pertemuan_map = {}
        for j in daftar_jadwal:
            pertemuan_map[j['id_jadwal']] = [] 
            
        for p in pertemuan_hari_ini_list:
            jadwal_id = p['id_jadwal']
            if jadwal_id in pertemuan_map:
                pertemuan_map[jadwal_id].append(p)
        
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
              AND p.tanggal_asli >= %s 
            ORDER BY p.tanggal_asli ASC
        """
        cursor.execute(sql_query_perubahan, (id_kelas_mhs, id_angkatan_mhs, today_date))
        perubahan_list = cursor.fetchall()
        
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
            
            sql_query = """
            SELECT 
                m.NIM, 
                m.Nama, 
                m.id_kelas, 
                m.id_angkatan,
                k.nama_kelas,   -- Data yang diperlukan
                a.tahun         -- Data yang diperlukan
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



# KELOLA DATA MAHASISWA

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
        
        try:

            cursor.execute("INSERT INTO mahasiswa (NIM, Nama, id_kelas, id_angkatan) VALUES (%s, %s, %s, %s)", 
                           (nim_baru, nama_baru, id_kelas_baru, id_angkatan_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error inserting data: {e}")

            
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

            cursor.execute("UPDATE kelas SET nama_kelas = %s,  WHERE id_kelas = %s",
                           (nama_kelas_baru))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error updating data: {e}")
        finally:
            cursor.close()
            conn.close()
            
            return redirect(url_for('admin_kelola_kelas'))


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

#============================ PAGE BIMBINGAN ==================================
@app.route('/dashboard/admin/kelola-bimbingan')
def admin_kelola_bimbingan():
    if session.get('role') == 'admin':
        return render_template('admin/kelola-bimbingan.html', user=session['username'])
    return redirect(url_for('login'))


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