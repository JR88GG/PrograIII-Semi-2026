import os
import mysql.connector
from mysql.connector import Error

class Conexion:
    def __init__(self):
        self.config = dict(host=os.getenv('DB_HOST', 'localhost'), user=os.getenv('DB_USER', 'root'), password=os.getenv('DB_PASSWORD', ''), database='db_academica')

    def conectar(self):
        return mysql.connector.connect(**self.config)

    def consultar(self, sql, datos=None):
        with self.conectar() as con:
            cursor = con.cursor(dictionary=True)
            try:
                cursor.execute(sql, datos or ())
                return cursor.fetchall()
            finally:
                cursor.close()

    def ejecutar(self, sql, datos=None):
        with self.conectar() as con:
            cursor = con.cursor()
            try:
                cursor.execute(sql, datos or ())
                con.commit()
                return cursor.rowcount
            except Exception:
                con.rollback()
                raise
            finally:
                cursor.close()
