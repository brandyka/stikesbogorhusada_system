import mysql.connector

def create_connection():
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="qwertyuiop",
            database="sbh",
            auth_plugin='mysql_native_password'
        )
        if conn.is_connected():
            print("Succesfully Connect Database")
            return conn
    except mysql.connector.Error as e:
        print("Fail Connect Database", e)
        return None

if __name__ == "__main__":
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")
        print("📦 Terhubung ke database:", cursor.fetchone()[0])
        conn.close()
