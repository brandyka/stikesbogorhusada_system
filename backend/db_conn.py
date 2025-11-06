import mysql.connector
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

def create_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DATABASE_NAME"),
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
