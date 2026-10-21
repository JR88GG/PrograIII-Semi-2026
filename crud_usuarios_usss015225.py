import hashlib
import hmac
import os
import re
from mysql.connector import Error, IntegrityError
from conexion import Conexion

TABLA = 'usuarios_usss015225'
db = Conexion()

def hash_clave(clave, sal=None):
    sal = sal or os.urandom(8)
    digest = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal, 120000, dklen=8)
    return (sal + digest).hex()  # 32 caracteres, cabe en CHAR(35)

def verificar_clave(clave, almacenada):
    try:
        bruto = bytes.fromhex(almacenada.strip())
        if len(bruto) != 16:
            return False
        return hmac.compare_digest(hash_clave(clave, bruto[:8]), almacenada.strip().lower())
    except (ValueError, AttributeError):
        return False

class crud_usuarios_usss015225:
    def consultar(self, buscar=''):
        return db.consultar(f'''SELECT idUsuario, usuario, nombre, `dirección` AS direccion, `teléfono` AS telefono
                                FROM {TABLA} WHERE usuario LIKE %s OR nombre LIKE %s
                                ORDER BY idUsuario DESC''', (f'%{buscar}%', f'%{buscar}%'))

    def autenticar(self, usuario, clave):
        filas = db.consultar(f'SELECT idUsuario, usuario, nombre, clave FROM {TABLA} WHERE usuario=%s', (usuario,))
        if filas and verificar_clave(clave, filas[0]['clave']):
            return {k: filas[0][k] for k in ('idUsuario', 'usuario', 'nombre')}
        return None

    def administrar(self, datos):
        accion = datos.get('accion')
        try:
            if accion == 'eliminar':
                id_usuario = int(datos['idUsuario'])
                n = db.ejecutar(f'DELETE FROM {TABLA} WHERE idUsuario=%s', (id_usuario,))
                return {'msg': 'ok' if n else 'Usuario no encontrado.'}
            if accion not in ('nuevo', 'modificar'):
                return {'msg': 'Acción no válida.'}
            usuario = str(datos.get('usuario', '')).strip()
            nombre = str(datos.get('nombre', '')).strip()
            direccion = str(datos.get('direccion', '')).strip()
            telefono = str(datos.get('telefono', '')).strip()
            clave = str(datos.get('clave', ''))
            if not usuario or not nombre or not direccion or not re.fullmatch(r'\d{4}-\d{4}', telefono):
                return {'msg': 'Complete los campos; teléfono debe tener formato 0000-0000.'}
            if len(usuario) > 35 or len(nombre) > 85 or len(direccion) > 100:
                return {'msg': 'Uno de los campos supera la longitud permitida.'}
            if accion == 'nuevo':
                if not clave or len(clave) < 6:
                    return {'msg': 'La clave debe tener al menos 6 caracteres.'}
                db.ejecutar(f'''INSERT INTO {TABLA} (usuario, clave, nombre, `dirección`, `teléfono`)
                               VALUES (%s,%s,%s,%s,%s)''', (usuario, hash_clave(clave), nombre, direccion, telefono))
            else:
                id_usuario = int(datos['idUsuario'])
                if clave:
                    if len(clave) < 6:
                        return {'msg': 'La nueva clave debe tener al menos 6 caracteres.'}
                    sql = f'''UPDATE {TABLA} SET usuario=%s, clave=%s, nombre=%s, `dirección`=%s, `teléfono`=%s WHERE idUsuario=%s'''
                    valores = (usuario, hash_clave(clave), nombre, direccion, telefono, id_usuario)
                else:
                    sql = f'''UPDATE {TABLA} SET usuario=%s, nombre=%s, `dirección`=%s, `teléfono`=%s WHERE idUsuario=%s'''
                    valores = (usuario, nombre, direccion, telefono, id_usuario)
                if not db.ejecutar(sql, valores):
                    return {'msg': 'Usuario no encontrado o sin cambios.'}
            return {'msg': 'ok'}
        except (ValueError, KeyError):
            return {'msg': 'Identificador inválido.'}
        except IntegrityError:
            return {'msg': 'El nombre de usuario ya está registrado.'}
        except Error as exc:
            return {'msg': f'Error de base de datos: {exc.msg}'}
