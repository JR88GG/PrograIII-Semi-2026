from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http import cookies
from pathlib import Path
import json
import secrets
import threading
from crud_usuarios_usss015225 import crud_usuarios_usss015225

PORT = 3000
DIRECTORIO = Path(__file__).resolve().parent
crudUsuarios = crud_usuarios_usss015225()
sesiones = {}
bloqueo = threading.Lock()

class miServidor(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORIO), **kwargs)

    def responderJson(self, datos, estado=200, cookie=None):
        contenido = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(estado)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def sesion(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
            token = jar['sesion'].value if 'sesion' in jar else None
        except cookies.CookieError:
            token = None
        with bloqueo:
            return token, sesiones.get(token)

    def do_POST(self):
        ruta = urlparse(self.path).path
        if ruta not in ('/login', '/logout', '/usuario'):
            return self.responderJson({'msg': 'Ruta no encontrada.'}, 404)
        try:
            longitud = int(self.headers.get('Content-Length', 0))
            if longitud < 0 or longitud > 16384:
                return self.responderJson({'msg': 'Solicitud demasiado grande.'}, 413)
            datos = json.loads(self.rfile.read(longitud).decode('utf-8'))
            if not isinstance(datos, dict):
                raise ValueError()
        except (ValueError, UnicodeError, json.JSONDecodeError):
            return self.responderJson({'msg': 'JSON inválido.'}, 400)
        try:
            if ruta == '/login':
                usuario = crudUsuarios.autenticar(str(datos.get('usuario', '')), str(datos.get('clave', '')))
                if not usuario:
                    return self.responderJson({'msg': 'Usuario o clave incorrectos.'}, 401)
                token = secrets.token_urlsafe(32)
                with bloqueo:
                    sesiones[token] = usuario
                return self.responderJson({'msg': 'ok', 'usuario': usuario}, cookie=f'sesion={token}; HttpOnly; SameSite=Strict; Path=/')
            token, sesion = self.sesion()
            if ruta == '/logout':
                with bloqueo:
                    sesiones.pop(token, None)
                return self.responderJson({'msg': 'ok'}, cookie='sesion=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if not sesion:
                return self.responderJson({'msg': 'Debe iniciar sesión.'}, 401)
            return self.responderJson(crudUsuarios.administrar(datos))
        except Exception as exc:
            print('Error:', exc)
            return self.responderJson({'msg': 'Error interno del servidor.'}, 500)

    def do_GET(self):
        ruta = urlparse(self.path)
        if ruta.path == '/sesion':
            _, sesion = self.sesion()
            return self.responderJson({'autenticado': bool(sesion), 'usuario': sesion})
        if ruta.path == '/usuarios':
            _, sesion = self.sesion()
            if not sesion:
                return self.responderJson({'msg': 'Debe iniciar sesión.'}, 401)
            try:
                buscar = parse_qs(ruta.query).get('buscar', [''])[0]
                return self.responderJson(crudUsuarios.consultar(buscar))
            except Exception as exc:
                print('Error:', exc)
                return self.responderJson({'msg': 'Error al consultar.'}, 500)
        if ruta.path in ('/', '/index.html'):
            self.path = '/index.html'
            return super().do_GET()
        return self.send_error(404)

if __name__ == '__main__':
    print(f'Servidor en http://localhost:{PORT}')
    HTTPServer(('localhost', PORT), miServidor).serve_forever()
