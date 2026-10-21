# Parcial II - USSS015225

Proyecto adaptado de la estructura original: `server.py` (HTTP), `conexion.py` (MySQL), módulo CRUD, `index.html` (Bootstrap + fetch).

## Requisitos
- Python 3.10+ y MySQL 8+
- Instalar dependencias: `pip install -r requirements.txt`
- Ejecutar `db_academica_usss015225.sql` en MySQL (por ejemplo: `mysql -u root -p < db_academica_usss015225.sql`).
- Configurar la conexión mediante `DB_HOST`, `DB_USER`, `DB_PASSWORD` si no son los valores predeterminados (localhost, root, contraseña vacía).

## Primer acceso
1. Ejecutar `python crear_usuario_inicial.py` y completar los datos del primer usuario.
2. Ejecutar `python server.py`.
3. Abrir `http://localhost:3000` e iniciar sesión con el usuario creado.
4. Registrar, buscar, editar y eliminar usuarios desde el panel.

## Correspondencia con el parcial
1. Base de datos `db_academica`, tabla `usuarios_usss015225` y seis campos solicitados.
2. Formulario de usuarios y JavaScript con `fetch()`.
3. Clase `crud_usuarios_usss015225` para guardar en MySQL.
4. Búsqueda por usuario/nombre, edición y eliminación.
5. Login inicial con verificación de credenciales en MySQL y cookie de sesión HTTP-only.

Las contraseñas se almacenan como un hash PBKDF2 compacto para ajustarse al `CHAR(35)` exigido. No se devuelven las contraseñas en las consultas. La aplicación está orientada a uso local/académico, no a despliegue público sin HTTPS, protección CSRF y endurecimiento adicional.
