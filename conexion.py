import mysql.connector
from mysql.connector import Error


class Conexion:
    def __init__(self):
        self.host = "localhost"
        self.user = "root"
        self.password = ""
        self.database = "db_sistema_impuestos"
        print("Conectando a la base de datos...")

        try:
            self.conexion = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            if self.conexion.is_connected():
                print("Conexion exitosa")
            else:
                print("No se pudo conectar a la base de datos")
        except Error as e:
            print(f"Error al conectar a la base de datos: {e}")

    # 'datos' es opcional: crud_clientes sigue llamando consultar(sql)
    def consultar(self, sql, datos=None):
        try:
            cursor = self.conexion.cursor(dictionary=True)
            cursor.execute(sql, datos)
            filas = cursor.fetchall()
            # Cierra la transaccion implicita para ver siempre datos frescos (InnoDB)
            self.conexion.commit()
            return filas
        except Error as e:
            print(f"Error al consultar la base de datos: {e}")
            return None

    def ejecutar(self, sql, datos):
        try:
            cursor = self.conexion.cursor()
            cursor.execute(sql, datos)
            self.conexion.commit()
            return 'ok'
        except Error as e:
            print(f"Error al ejecutar la consulta: {e}")
            return f'Error: {e}'

    # Ejecuta varias sentencias [(sql, datos), ...] en UNA transaccion.
    # Si alguna falla se revierte todo. Devuelve la lista de lastrowid
    # (uno por sentencia) o un texto 'Error: ...'.
    def transaccion(self, operaciones):
        try:
            cursor = self.conexion.cursor()
            ids = []
            for sql, datos in operaciones:
                cursor.execute(sql, datos)
                ids.append(cursor.lastrowid)
            self.conexion.commit()
            return ids
        except Error as e:
            self.conexion.rollback()
            print(f"Error en la transaccion: {e}")
            return f'Error: {e}'
