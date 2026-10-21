from getpass import getpass
from crud_usuarios_usss015225 import crud_usuarios_usss015225

if __name__ == '__main__':
    print('Creación del primer usuario (ejecutar después del archivo SQL).')
    datos = {'accion': 'nuevo', 'usuario': input('Usuario: ').strip(), 'clave': getpass('Clave (mínimo 6 caracteres): '),
             'nombre': input('Nombre: ').strip(), 'direccion': input('Dirección: ').strip(), 'telefono': input('Teléfono (0000-0000): ').strip()}
    print(crud_usuarios_usss015225().administrar(datos)['msg'])
