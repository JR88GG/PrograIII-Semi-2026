from mysql.connector.errors import Error
import conexion

db = conexion.Conexion()

class crud_clientes:
    def consultar(self, buscar):
        # Parametrizado: un apostrofe o comilla en el nombre ya no rompe la consulta
        return db.consultar("SELECT * FROM clientes WHERE nombre LIKE %s ORDER BY nombre", (f"%{buscar}%",))

    def administrar(self, datos):
        try:
            if datos['accion']=='nuevo':
                sql = """
                    INSERT INTO clientes(codigo,nombre,direccion,telefono,email,tipo)
                    VALUES(%s,%s,%s,%s,%s,%s)
                """
                valores = (datos['codigo'],datos['nombre'],datos['direccion'],datos['telefono'],datos['email'],datos['tipo'])
            elif datos['accion']=='modificar':
                sql = """
                    UPDATE clientes SET codigo=%s,nombre=%s,direccion=%s,telefono=%s,email=%s,tipo=%s
                    WHERE idCliente=%s
                """
                valores = (datos['codigo'],datos['nombre'],datos['direccion'],datos['telefono'],datos['email'],datos['tipo'],datos['idCliente'])
            elif datos['accion']=='eliminar':
                # clientes es MyISAM (sin llaves foraneas): se valida aqui para no dejar periodos huerfanos
                usados = db.consultar("SELECT COUNT(*) AS n FROM periodos WHERE idCliente=%s", (datos['idCliente'],))
                if usados is None:
                    return "Error al verificar los períodos del cliente."
                if usados[0]['n'] > 0:
                    return "No se puede eliminar: el cliente tiene períodos registrados."
                sql = """
                    DELETE FROM clientes WHERE idCliente=%s
                """
                valores = (datos['idCliente'],)
            else:
                return "Acción no válida."
            return db.ejecutar(sql,valores)
        except Error as e:
            return f"Error al guardar el cliente: {e}"
