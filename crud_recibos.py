from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
import conexion

db = conexion.Conexion()

CENTAVOS = Decimal('0.01')

MSG_PRODUCTO = 'Confirme si la actividad corresponde a comercio o industria.'
MSG_FECHAS = 'La fecha Hasta debe ser posterior a la fecha Desde.'
MSG_RECIBO_EXISTE = 'Ya existe un recibo que cubre parte del rango indicado.'


class crud_recibos:
    # ---------- Consultas ----------
    def consultar(self, idCliente, idProducto=''):
        sql = """
            SELECT r.*, pr.codigo
            FROM recibos r
            INNER JOIN productos pr ON pr.idProducto = r.idProducto
            WHERE r.idCliente = %s
        """
        valores = [idCliente]
        if idProducto:
            sql += " AND r.idProducto = %s"
            valores.append(idProducto)
        sql += " ORDER BY r.cobro_desde DESC, r.idRecibo DESC"
        return db.consultar(sql, tuple(valores)) or []

    # ---------- Utilidades ----------
    def _fecha(self, valor):
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date):
            return valor
        try:
            return datetime.strptime(str(valor), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    def _recibos_existentes(self, idCliente, idProducto, desde, hasta):
        return db.consultar("""
            SELECT idRecibo, cobro_desde, cobro_hasta, total
            FROM recibos
            WHERE idCliente = %s AND idProducto = %s
              AND cobro_desde < %s AND cobro_hasta > %s
            ORDER BY cobro_desde
        """, (idCliente, idProducto, hasta, desde)) or []

    # ---------- Calculo del cargo (seccion 15) ----------
    # Cargo del periodo = Cantidad x Precio mensual x Meses aplicables
    # Solo se usan los periodos que se superponen con el rango de cobro.
    def _calcular_cargo(self, datos):
        cliente = db.consultar("SELECT idCliente FROM clientes WHERE idCliente = %s", (datos.get('idCliente'),))
        if not cliente:
            return {'msg': 'Seleccione un cliente registrado.'}
        producto = db.consultar("SELECT idProducto FROM productos WHERE idProducto = %s", (datos.get('idProducto'),))
        if not producto:
            return {'msg': MSG_PRODUCTO}

        cobro_desde = self._fecha(datos.get('cobro_desde'))
        cobro_hasta = self._fecha(datos.get('cobro_hasta'))
        if not cobro_desde or not cobro_hasta or cobro_desde >= cobro_hasta:
            return {'msg': MSG_FECHAS}

        periodos = db.consultar("""
            SELECT idPeriodo, desde, hasta, cantidad, precio
            FROM periodos
            WHERE idCliente = %s AND idProducto = %s AND desde < %s AND hasta > %s
            ORDER BY desde
        """, (cliente[0]['idCliente'], producto[0]['idProducto'], cobro_hasta, cobro_desde)) or []
        if not periodos:
            return {'msg': 'No existe un período registrado para el rango de cobro indicado.'}

        lineas = []
        advertencias = []
        cursor = cobro_desde
        for p in periodos:
            inicio = max(p['desde'], cobro_desde)
            fin = min(p['hasta'], cobro_hasta)

            # Espacios sin cobertura: no se cobran ni se usa un precio general
            if inicio > cursor:
                advertencias.append(f"No hay período registrado entre {cursor} y {inicio}; ese tramo no se cobra.")

            # Meses completos dentro de la vigencia
            if inicio.day != fin.day:
                return {'msg': (f"El rango de cobro no coincide con meses completos del período "
                                f"{p['desde']} a {p['hasta']}. Ajuste las fechas del cobro.")}
            meses = (fin.year * 12 + fin.month) - (inicio.year * 12 + inicio.month)
            importe = (p['cantidad'] * p['precio'] * meses).quantize(CENTAVOS, ROUND_HALF_UP)
            lineas.append({
                'idPeriodo': p['idPeriodo'],
                'desde': inicio,
                'hasta': fin,
                'meses': meses,
                'cantidad': p['cantidad'],
                'precio': p['precio'],
                'importe': importe
            })
            cursor = fin

        if cursor < cobro_hasta:
            advertencias.append(f"No hay período registrado entre {cursor} y {cobro_hasta}; ese tramo no se cobra.")

        return {
            'msg': 'ok',
            'idCliente': cliente[0]['idCliente'],
            'idProducto': producto[0]['idProducto'],
            'cobro_desde': cobro_desde,
            'cobro_hasta': cobro_hasta,
            'lineas': lineas,
            'total': sum((l['importe'] for l in lineas), Decimal('0')),
            'advertencias': advertencias
        }

    # ---------- Acciones ----------
    def administrar(self, datos):
        try:
            accion = datos.get('accion')
            if accion == 'cargo':
                return self._cargo(datos)
            elif accion == 'generar':
                return self._generar(datos)
            return {'msg': 'Acción no válida.'}
        except Exception as e:
            return {'msg': f"Error al procesar el recibo: {e}"}

    # Solo muestra el cargo, no guarda nada
    def _cargo(self, datos):
        res = self._calcular_cargo(datos)
        if res['msg'] != 'ok':
            return res
        res['conflictos'] = self._recibos_existentes(res['idCliente'], res['idProducto'], res['cobro_desde'], res['cobro_hasta'])
        return res

    def _generar(self, datos):
        res = self._calcular_cargo(datos)
        if res['msg'] != 'ok':
            return res
        if not datos.get('confirmado'):
            return {'msg': 'Se requiere la confirmación del usuario antes de guardar.'}

        # Evita cobrar dos veces el mismo tramo
        existentes = self._recibos_existentes(res['idCliente'], res['idProducto'], res['cobro_desde'], res['cobro_hasta'])
        if existentes:
            return {'msg': MSG_RECIBO_EXISTE, 'conflictos': existentes}

        usuario = datos.get('usuario') or 'sistema'
        operaciones = [
            (
                "INSERT INTO recibos(idCliente,idProducto,cobro_desde,cobro_hasta,total,usuario) VALUES(%s,%s,%s,%s,%s,%s)",
                (res['idCliente'], res['idProducto'], res['cobro_desde'], res['cobro_hasta'], res['total'], usuario)
            ),
            # El detalle tambien genera ids; se guarda el del recibo en una variable
            ("SET @idRecibo = LAST_INSERT_ID()", None)
        ]
        for l in res['lineas']:
            operaciones.append((
                """
                INSERT INTO recibos_detalle(idRecibo,idPeriodo,desde,hasta,meses,cantidad,precio,importe)
                VALUES(@idRecibo,%s,%s,%s,%s,%s,%s,%s)
                """,
                (l['idPeriodo'], l['desde'], l['hasta'], l['meses'], l['cantidad'], l['precio'], l['importe'])
            ))
            # RF 09: desde ahora el periodo no se recalcula de forma automatica
            operaciones.append(("UPDATE periodos SET facturado = 1 WHERE idPeriodo = %s", (l['idPeriodo'],)))
            operaciones.append((
                """
                INSERT INTO periodos_bitacora(idPeriodo,accion,motivo,usuario)
                VALUES(%s,'facturar',CONCAT('Incluido en el recibo #', @idRecibo, ' (cobro ', %s, ' a ', %s, ')'),%s)
                """,
                (l['idPeriodo'], res['cobro_desde'], res['cobro_hasta'], usuario)
            ))

        ids = db.transaccion(operaciones)
        if isinstance(ids, str):
            return {'msg': ids}
        return {'msg': 'ok', 'idRecibo': ids[0], 'total': res['total'], 'advertencias': res['advertencias']}
