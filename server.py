from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib import parse 
from urllib.parse import urlparse, parse_qs
import crud_clientes
import crud_periodos
import crud_recibos

import json

port = 3000
crudClientes = crud_clientes.crud_clientes()
crudPeriodos = crud_periodos.crud_periodos()
crudRecibos = crud_recibos.crud_recibos()

class miServidor(SimpleHTTPRequestHandler):
    def responderJson(self, datos):
        self.send_response(200)
        self.send_header("Content-type","application/json")
        self.end_headers()
        # default=str convierte Decimal y fechas a texto
        self.wfile.write(json.dumps(datos, default=str).encode("utf-8"))

    def do_POST(self):
        longitud = int(self.headers['Content-Length'])
        datos = self.rfile.read(longitud)
        datos = datos.decode("utf-8")
        datos = json.loads(datos)

        if self.path == "/periodo":
            respuesta = crudPeriodos.administrar(datos)
        elif self.path == "/recibo":
            respuesta = crudRecibos.administrar(datos)
        else:
            respuesta = {'msg': crudClientes.administrar(datos)}

        self.responderJson(respuesta)

    def do_GET(self):
        urlParse = urlparse(self.path)
        qs = parse_qs(urlParse.query)
       
        if urlParse.path == "/clientes":
            buscar = qs.get('buscar', [''])[0]
            print(buscar)
            datos = crudClientes.consultar(buscar)
            self.responderJson(datos)

        elif urlParse.path == "/productos":
            self.responderJson(crudPeriodos.productos())

        elif urlParse.path == "/periodos":
            idCliente = qs.get('idCliente', [''])[0]
            idProducto = qs.get('idProducto', [''])[0]
            self.responderJson(crudPeriodos.consultar(idCliente, idProducto))

        elif urlParse.path == "/recibos":
            idCliente = qs.get('idCliente', [''])[0]
            idProducto = qs.get('idProducto', [''])[0]
            self.responderJson(crudRecibos.consultar(idCliente, idProducto))

        elif urlParse.path == "/periodos/bitacora":
            idPeriodo = qs.get('idPeriodo', [''])[0]
            self.responderJson(crudPeriodos.bitacora(idPeriodo))
        
        elif self.path == "/":
            self.path = "/index.html"
            return SimpleHTTPRequestHandler.do_GET(self)

        else:
            self.send_error(404)

print(f"Servidor corriendo en el puerto {port}")
server = HTTPServer(("localhost",port),miServidor)
server.serve_forever()
