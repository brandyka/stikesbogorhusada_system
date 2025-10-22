import mysql.connector

def create_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",       # host database kamu
            user="root",            # username MySQL
            password="qwertyuiop",            # password MySQL (kosong kalau default di XAMPP)
            database="sbh" # nama database kamu
        )

        if conn.is_connected():
            print("✅ Koneksi ke database berhasil!")
            return conn

    except mysql.connector.Error as e:
        print("❌ Gagal konek ke database:", e)
        return None