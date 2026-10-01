from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from datetime import date, datetime
import hashlib
import hmac
import conexion

db = conexion.Conexion()

VERSION_FORMULA = 'bloques-v1'
BLOQUE = Decimal('1000')
CENTAVOS = Decimal('0.01')

MSG_NO_EMPRESA = 'El Impuesto a las Actividades Económicas requiere un cliente de tipo empresa.'
MSG_BALANCE = 'Ingrese un balance mayor que cero.'
MSG_FECHAS = 'La fecha Hasta debe ser posterior a la fecha Desde.'
MSG_SUPERPUESTO = 'El período indicado se superpone con un período existente.'
MSG_SIN_TARIFA = 'No existe una tarifa configurada para el balance indicado.'
MSG_TARIFAS_DUP = 'Existe más de una tarifa aplicable. Corrija la tabla tarifaria.'
MSG_PRODUCTO = 'Confirme si la actividad corresponde a comercio o industria.'
MSG_FACTURADO = 'El período ya fue utilizado en recibos y no puede recalcularse automáticamente.'


def dinero(valor):
    return f"{valor:,.2f}"


class crud_periodos:
    # ---------- Consultas ----------
    def productos(self):
        return db.consultar("SELECT idProducto, codigo, nombre, tipo_actividad FROM productos ORDER BY codigo")

    def consultar(self, idCliente, idProducto=''):
        sql = """
            SELECT p.*, pr.codigo, pr.nombre AS producto,
                   IF(CURDATE() >= p.desde AND CURDATE() < p.hasta, 'Vigente',
                      IF(p.hasta <= CURDATE(), 'Histórico', 'Futuro')) AS estado
            FROM periodos p
            INNER JOIN productos pr ON pr.idProducto = p.idProducto
            WHERE p.idCliente = %s
        """
        valores = [idCliente]
        if idProducto:
            sql += " AND p.idProducto = %s"
            valores.append(idProducto)
        sql += " ORDER BY p.desde DESC"
        filas = db.consultar(sql, tuple(valores)) or []

        vigentes = [f['subtotal'] for f in filas if f['estado'] == 'Vigente']
        return {
            # RF 21: mensualidad vigente vs. total administrativo (solo referencial)
            'impuesto_vigente': sum(vigentes, Decimal('0')) if vigentes else None,
            'total_referencial': sum((f['precio'] for f in filas), Decimal('0')),
            'periodos': filas
        }

    def bitacora(self, idPeriodo):
        return db.consultar(
            "SELECT * FROM periodos_bitacora WHERE idPeriodo = %s ORDER BY fecha DESC, idBitacora DESC",
            (idPeriodo,)
        )

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

    def _decimal(self, valor, defecto=None):
        try:
            numero = Decimal(str(valor).strip())
            return numero if numero.is_finite() else defecto
        except (InvalidOperation, AttributeError):
            return defecto

    def _conflictos(self, idCliente, idProducto, desde, hasta, excluir=0):
        # [desde, hasta) se superpone si: existente.desde < nuevo.hasta Y existente.hasta > nuevo.desde
        return db.consultar("""
            SELECT idPeriodo, desde, hasta, monto, precio, facturado
            FROM periodos
            WHERE idCliente = %s AND idProducto = %s
              AND desde < %s AND hasta > %s AND idPeriodo <> %s
            ORDER BY desde
        """, (idCliente, idProducto, hasta, desde, excluir)) or []

    def _advertencias(self, idCliente, idProducto, desde, hasta, excluir=0):
        # RF 06: avisar si queda un espacio sin cobertura (no bloquea el guardado)
        avisos = []
        anterior = db.consultar("""
            SELECT MAX(hasta) AS h FROM periodos
            WHERE idCliente = %s AND idProducto = %s AND hasta <= %s AND idPeriodo <> %s
        """, (idCliente, idProducto, desde, excluir))
        if anterior and anterior[0]['h'] and anterior[0]['h'] < desde:
            avisos.append(f"Existe un espacio sin cobertura entre {anterior[0]['h']} y {desde}.")
        siguiente = db.consultar("""
            SELECT MIN(desde) AS d FROM periodos
            WHERE idCliente = %s AND idProducto = %s AND desde >= %s AND idPeriodo <> %s
        """, (idCliente, idProducto, hasta, excluir))
        if siguiente and siguiente[0]['d'] and siguiente[0]['d'] > hasta:
            avisos.append(f"Existe un espacio sin cobertura entre {hasta} y {siguiente[0]['d']}.")
        return avisos

    # ---------- Calculo (RF 10 al RF 13, seccion 10) ----------
    def _calcular(self, datos):
        cliente = db.consultar(
            "SELECT idCliente, codigo, nombre, tipo FROM clientes WHERE idCliente = %s",
            (datos.get('idCliente'),)
        )
        if not cliente:
            return {'msg': 'Seleccione un cliente registrado.'}
        if cliente[0]['tipo'] != 'empresa':
            return {'msg': MSG_NO_EMPRESA}

        producto = db.consultar(
            "SELECT idProducto, codigo, nombre FROM productos WHERE idProducto = %s",
            (datos.get('idProducto'),)
        )
        if not producto:
            return {'msg': MSG_PRODUCTO}

        desde = self._fecha(datos.get('desde'))
        hasta = self._fecha(datos.get('hasta'))
        if not desde or not hasta or desde >= hasta:
            return {'msg': MSG_FECHAS}

        monto = self._decimal(datos.get('monto'))
        if monto is None or monto <= 0:
            return {'msg': MSG_BALANCE}

        cantidad = self._decimal(datos.get('cantidad'), Decimal('1.00'))
        if cantidad <= 0:
            return {'msg': 'La cantidad debe ser mayor que cero.'}

        # RF 10: TarifaDesde <= Balance <= TarifaHasta, vigente a la fecha Desde del periodo
        tarifas = db.consultar("""
            SELECT * FROM tarifas
            WHERE idProducto = %s
              AND vigencia_desde <= %s
              AND (vigencia_hasta IS NULL OR vigencia_hasta > %s)
              AND desde <= %s AND hasta >= %s
        """, (producto[0]['idProducto'], desde, desde, monto, monto))
        if tarifas is None:
            return {'msg': 'Error al consultar las tarifas.'}
        if len(tarifas) == 0:
            return {'msg': MSG_SIN_TARIFA}          # RF 11 / RF 13: sin precio general
        if len(tarifas) > 1:
            return {'msg': MSG_TARIFAS_DUP}         # RF 12

        t = tarifas[0]
        excedente = max(monto - t['desde'], Decimal('0'))

        if t['porcentaje'] > 0:
            # 10.4 Tarifa porcentual (el porcentaje no se trunca)
            bloques = None
            impuesto = monto * t['porcentaje'] / 100
            formula = f"{dinero(monto)} x {t['porcentaje'].normalize():f} / 100"
        else:
            # 10.1 Tarifa por bloques completos
            bloques = int((excedente / BLOQUE).to_integral_value(ROUND_CEILING))
            impuesto = t['precio_base'] + (bloques * t['adicional'])
            formula = (f"{dinero(t['precio_base'])} + (CEIL({dinero(excedente)} / 1,000) x {dinero(t['adicional'])})"
                       f" = {dinero(t['precio_base'])} + ({bloques} x {dinero(t['adicional'])})")

        # Seccion 11: redondeo a 2 decimales solo al final
        precio = impuesto.quantize(CENTAVOS, ROUND_HALF_UP)
        subtotal = (cantidad * precio).quantize(CENTAVOS, ROUND_HALF_UP)
        formula += f" = {dinero(precio)}"

        return {
            'msg': 'ok',
            'cliente': cliente[0],
            'producto': producto[0],
            'calculo': {
                'idCliente': cliente[0]['idCliente'],
                'idProducto': producto[0]['idProducto'],
                'desde': desde,
                'hasta': hasta,
                'balance': monto,
                'idTarifa': t['idTarifa'],
                'tarifa_version': t['version'],
                'rango_desde': t['desde'],
                'rango_hasta': t['hasta'],
                'precio_base': t['precio_base'],
                'excedente': excedente,
                'bloques': bloques,
                'adicional': t['adicional'],
                'porcentaje': t['porcentaje'],
                'precio': precio,
                'cantidad': cantidad,
                'subtotal': subtotal,
                'formula': formula,
                'version_formula': VERSION_FORMULA
            }
        }

    # ---------- Acciones ----------
    def administrar(self, datos):
        try:
            accion = datos.get('accion')
            if accion == 'calcular':
                return self._previsualizar(datos)
            elif accion == 'nuevo':
                return self._nuevo(datos)
            elif accion == 'recalcular':
                return self._recalcular(datos)
            elif accion == 'corregir':
                return self._corregir(datos)
            return {'msg': 'Acción no válida.'}
        except Exception as e:
            return {'msg': f"Error al guardar el período: {e}"}

    # Paso 6 del flujo: calcula y muestra el detalle SIN guardar (RF 17 / RF 18)
    def _previsualizar(self, datos):
        res = self._calcular(datos)
        if res['msg'] != 'ok':
            return res
        c = res['calculo']
        res['conflictos'] = self._conflictos(c['idCliente'], c['idProducto'], c['desde'], c['hasta'])
        res['advertencias'] = self._advertencias(c['idCliente'], c['idProducto'], c['desde'], c['hasta'])
        return res

    def _nuevo(self, datos):
        res = self._calcular(datos)
        if res['msg'] != 'ok':
            return res
        c = res['calculo']
        usuario = datos.get('usuario') or 'sistema'

        # Paso 7: confirmacion explicita del usuario
        if not datos.get('confirmado'):
            return {'msg': 'Se requiere la confirmación del usuario antes de guardar.'}

        operaciones = []
        conflictos = self._conflictos(c['idCliente'], c['idProducto'], c['desde'], c['hasta'])
        if conflictos:
            # RF 07: si cambia el balance se cierra el periodo vigente (no se sobrescribe)
            viejo = conflictos[0]
            puede_cerrar = (
                datos.get('cerrar_vigente')
                and len(conflictos) == 1
                and viejo['desde'] < c['desde']
                and viejo['hasta'] <= c['hasta']
            )
            if puede_cerrar and viejo['facturado']:
                return {'msg': MSG_FACTURADO, 'conflictos': conflictos}
            if not puede_cerrar:
                return {'msg': MSG_SUPERPUESTO, 'conflictos': conflictos}   # CA 14
            operaciones.append((
                "UPDATE periodos SET hasta=%s, modificado_por=%s, modificado_en=NOW() WHERE idPeriodo=%s",
                (c['desde'], usuario, viejo['idPeriodo'])
            ))
            operaciones.append((
                "INSERT INTO periodos_bitacora(idPeriodo,accion,motivo,usuario) VALUES(%s,'cerrar',%s,%s)",
                (viejo['idPeriodo'], f"Cierre por nuevo período desde {c['desde']}", usuario)
            ))

        posicion = len(operaciones)
        operaciones.append((
            """
            INSERT INTO periodos(idCliente,idProducto,desde,hasta,monto,cantidad,precio,subtotal,
                                 idTarifa,tarifa_desde,tarifa_hasta,tarifa_precio_base,tarifa_adicional,
                                 tarifa_porcentaje,formula,version_formula,fecha_calculo,creado_por)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s)
            """,
            (c['idCliente'], c['idProducto'], c['desde'], c['hasta'], c['balance'], c['cantidad'],
             c['precio'], c['subtotal'], c['idTarifa'], c['rango_desde'], c['rango_hasta'],
             c['precio_base'], c['adicional'], c['porcentaje'], c['formula'], c['version_formula'], usuario)
        ))
        operaciones.append((
            """
            INSERT INTO periodos_bitacora(idPeriodo,accion,monto_nuevo,precio_nuevo,motivo,usuario)
            VALUES(LAST_INSERT_ID(),'crear',%s,%s,%s,%s)
            """,
            (c['balance'], c['precio'], c['formula'], usuario)
        ))

        # Seccion 17: todo dentro de una transaccion
        ids = db.transaccion(operaciones)
        if isinstance(ids, str):
            return {'msg': ids}
        return {
            'msg': 'ok',
            'idPeriodo': ids[posicion],
            'calculo': c,
            'advertencias': self._advertencias(c['idCliente'], c['idProducto'], c['desde'], c['hasta'], ids[posicion])
        }

    # Recalculo de un periodo NO facturado (RF 09)
    def _recalcular(self, datos):
        filas = db.consultar("SELECT * FROM periodos WHERE idPeriodo = %s", (datos.get('idPeriodo'),))
        if not filas:
            return {'msg': 'El período indicado no existe.'}
        p = filas[0]
        if p['facturado']:
            return {'msg': MSG_FACTURADO}

        res = self._calcular({
            'idCliente': p['idCliente'], 'idProducto': p['idProducto'],
            'desde': p['desde'], 'hasta': p['hasta'],
            'monto': datos.get('monto', p['monto']),
            'cantidad': datos.get('cantidad', p['cantidad'])
        })
        if res['msg'] != 'ok':
            return res
        c = res['calculo']
        usuario = datos.get('usuario') or 'sistema'

        if not datos.get('confirmado'):
            return {'msg': 'Se requiere la confirmación del usuario antes de guardar.'}

        ids = db.transaccion([
            (
                """
                UPDATE periodos SET monto=%s,cantidad=%s,precio=%s,subtotal=%s,idTarifa=%s,
                       tarifa_desde=%s,tarifa_hasta=%s,tarifa_precio_base=%s,tarifa_adicional=%s,
                       tarifa_porcentaje=%s,formula=%s,version_formula=%s,fecha_calculo=NOW(),
                       modificado_por=%s,modificado_en=NOW()
                WHERE idPeriodo=%s
                """,
                (c['balance'], c['cantidad'], c['precio'], c['subtotal'], c['idTarifa'],
                 c['rango_desde'], c['rango_hasta'], c['precio_base'], c['adicional'],
                 c['porcentaje'], c['formula'], c['version_formula'], usuario, p['idPeriodo'])
            ),
            (
                """
                INSERT INTO periodos_bitacora(idPeriodo,accion,monto_anterior,monto_nuevo,
                                              precio_anterior,precio_nuevo,motivo,usuario)
                VALUES(%s,'recalcular',%s,%s,%s,%s,%s,%s)
                """,
                (p['idPeriodo'], p['monto'], c['balance'], p['precio'], c['precio'],
                 datos.get('motivo') or 'Recálculo de período no facturado', usuario)
            )
        ])
        if isinstance(ids, str):
            return {'msg': ids}
        return {'msg': 'ok', 'idPeriodo': p['idPeriodo'], 'calculo': c}

    # ---------- Correccion retroactiva (RF 16) ----------
    # clave_hash = SHA2(CONCAT(salt, clave), 256), igual que en db_recibos.sql
    def _autorizar(self, usuario, clave):
        if not usuario or not clave:
            return None
        filas = db.consultar(
            "SELECT usuario, salt, clave_hash FROM autorizadores WHERE usuario = %s AND activo = 1",
            (usuario,)
        )
        if not filas:
            return None
        calculado = hashlib.sha256((filas[0]['salt'] + str(clave)).encode('utf-8')).hexdigest()
        return filas[0] if hmac.compare_digest(calculado, filas[0]['clave_hash']) else None

    # Corrige un periodo YA facturado: exige autorizador, motivo y deja bitacora.
    # Los recibos emitidos conservan su importe original (recibos_detalle guarda una copia).
    def _corregir(self, datos):
        filas = db.consultar("SELECT * FROM periodos WHERE idPeriodo = %s", (datos.get('idPeriodo'),))
        if not filas:
            return {'msg': 'El período indicado no existe.'}
        p = filas[0]
        if not p['facturado']:
            return {'msg': 'El período no ha sido facturado; use Recalcular.'}

        motivo = (datos.get('motivo') or '').strip()
        if len(motivo) < 10:
            return {'msg': 'Indique el motivo de la corrección (mínimo 10 caracteres).'}

        autorizador = self._autorizar(datos.get('autorizador'), datos.get('clave'))
        if not autorizador:
            return {'msg': 'Autorización inválida. Verifique el usuario y la clave.'}

        res = self._calcular({
            'idCliente': p['idCliente'], 'idProducto': p['idProducto'],
            'desde': p['desde'], 'hasta': p['hasta'],
            'monto': datos.get('monto'),
            'cantidad': p['cantidad']
        })
        if res['msg'] != 'ok':
            return res
        c = res['calculo']

        if not datos.get('confirmado'):
            return {'msg': 'Se requiere la confirmación del usuario antes de guardar.'}

        ids = db.transaccion([
            (
                """
                UPDATE periodos SET monto=%s,precio=%s,subtotal=%s,idTarifa=%s,
                       tarifa_desde=%s,tarifa_hasta=%s,tarifa_precio_base=%s,tarifa_adicional=%s,
                       tarifa_porcentaje=%s,formula=%s,version_formula=%s,fecha_calculo=NOW(),
                       modificado_por=%s,modificado_en=NOW()
                WHERE idPeriodo=%s
                """,
                (c['balance'], c['precio'], c['subtotal'], c['idTarifa'],
                 c['rango_desde'], c['rango_hasta'], c['precio_base'], c['adicional'],
                 c['porcentaje'], c['formula'], c['version_formula'],
                 autorizador['usuario'], p['idPeriodo'])
            ),
            (
                """
                INSERT INTO periodos_bitacora(idPeriodo,accion,monto_anterior,monto_nuevo,
                                              precio_anterior,precio_nuevo,motivo,usuario)
                VALUES(%s,'corregir',%s,%s,%s,%s,%s,%s)
                """,
                (p['idPeriodo'], p['monto'], c['balance'], p['precio'], c['precio'],
                 motivo, autorizador['usuario'])
            )
        ])
        if isinstance(ids, str):
            return {'msg': ids}
        return {'msg': 'ok', 'idPeriodo': p['idPeriodo'], 'calculo': c}
