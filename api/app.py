from flask import Flask, request, jsonify
from flask_cors import CORS
import pyodbc
import bcrypt
import jwt
import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)

SECRET_KEY = "finanzas-secret-key-2024"

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=FinanzasPersonales;"
    "Trusted_Connection=yes;"
)


def conectar_sql():
    return pyodbc.connect(CONNECTION_STRING)


# ── MIDDLEWARE: verificar token JWT ──────────────────────────────────────────
def token_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"ok": False, "error": "Token requerido"}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.usuario_id = payload["usuario_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"ok": False, "error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"ok": False, "error": "Token inválido"}), 401
        return f(*args, **kwargs)
    return decorador


# ── POST /registro ────────────────────────────────────────────────────────────
@app.route("/registro", methods=["POST"])
def registro():
    try:
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"ok": False, "error": "Usuario y contraseña requeridos"}), 400

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)",
            username, password_hash
        )
        cn.commit()
        cursor.close()
        cn.close()

        return jsonify({"ok": True, "mensaje": "Usuario creado correctamente"})

    except Exception as e:
        if "UNIQUE" in str(e) or "unique" in str(e) or "2627" in str(e) or "2601" in str(e):
            return jsonify({"ok": False, "error": "Ese usuario ya existe"}), 409
        return jsonify({"ok": False, "error": str(e)}), 500


# ── POST /login ───────────────────────────────────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    try:
        data     = request.get_json()
        username = data.get("usuario", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"ok": False, "error": "Usuario y contraseña requeridos"}), 400

        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(
            "SELECT id_usuario, password_hash FROM usuarios WHERE username = ?", username
        )
        row = cursor.fetchone()
        cursor.close()
        cn.close()

        if not row:
            return jsonify({"ok": False, "error": "Usuario o contraseña incorrectos"}), 401

        usuario_id    = row[0]
        password_hash = row[1].encode("utf-8")

        if not bcrypt.checkpw(password.encode("utf-8"), password_hash):
            return jsonify({"ok": False, "error": "Usuario o contraseña incorrectos"}), 401

        # Generar JWT con expiración de 8 horas
        token = jwt.encode(
            {
                "usuario_id": usuario_id,
                "username":   username,
                "exp":        datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            },
            SECRET_KEY,
            algorithm="HS256"
        )

        return jsonify({"ok": True, "token": token})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GET /categorias ───────────────────────────────────────────────────────────
@app.route("/categorias", methods=["GET"])
@token_requerido
def obtener_categorias():
    try:
        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute("SELECT id_categoria, nombre, tipo FROM categorias ORDER BY id_categoria")
        categorias = [{"id_categoria": r[0], "nombre": r[1], "tipo": r[2]} for r in cursor.fetchall()]
        cursor.close()
        cn.close()
        return jsonify({"ok": True, "categorias": categorias})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── POST /guardar ─────────────────────────────────────────────────────────────
@app.route("/guardar", methods=["POST"])
@token_requerido
def guardar():
    try:
        data   = request.get_json()
        uid    = request.usuario_id
        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(
            "INSERT INTO movimientos (fecha, id_categoria, descripcion, monto, id_usuario) VALUES (?, ?, ?, ?, ?)",
            data["fecha"], data["categoria"], data["descripcion"], data["monto"], uid
        )
        cn.commit()
        cursor.close()
        cn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GET /resumen ──────────────────────────────────────────────────────────────
@app.route("/resumen", methods=["GET"])
@token_requerido
def resumen():
    try:
        uid    = request.usuario_id
        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute("""
            SELECT
                SUM(CASE WHEN c.tipo = 'Ingreso' THEN m.monto ELSE 0 END),
                SUM(CASE WHEN c.tipo = 'Gasto'   THEN m.monto ELSE 0 END)
            FROM movimientos m
            INNER JOIN categorias c ON m.id_categoria = c.id_categoria
            WHERE m.id_usuario = ?
        """, uid)
        row      = cursor.fetchone()
        cursor.close()
        cn.close()
        ingresos = float(row[0]) if row[0] else 0.0
        gastos   = float(row[1]) if row[1] else 0.0
        return jsonify({"ok": True, "ingresos": ingresos, "gastos": gastos, "balance": ingresos + gastos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GET /movimientos ──────────────────────────────────────────────────────────
@app.route("/movimientos", methods=["GET"])
@token_requerido
def movimientos():
    try:
        uid       = request.usuario_id
        mes       = request.args.get("mes")
        categoria = request.args.get("categoria")

        query = """
            SELECT
                m.id_movimiento,
                m.id_categoria,
                CONVERT(varchar(10), m.fecha, 23) AS fecha,
                c.nombre AS categoria,
                c.tipo,
                m.descripcion,
                m.monto
            FROM movimientos m
            INNER JOIN categorias c ON m.id_categoria = c.id_categoria
            WHERE m.id_usuario = ?
        """
        params = [uid]

        if mes:
            query += " AND FORMAT(m.fecha, 'yyyy-MM') = ?"
            params.append(mes)
        if categoria:
            query += " AND m.id_categoria = ?"
            params.append(int(categoria))

        query += " ORDER BY m.id_movimiento DESC"

        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(query, *params)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        cn.close()
        return jsonify({"ok": True, "movimientos": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GET /resumen-categorias ───────────────────────────────────────────────────
@app.route("/resumen-categorias", methods=["GET"])
@token_requerido
def resumen_categorias():
    try:
        uid    = request.usuario_id
        mes    = request.args.get("mes")

        query = """
            SELECT c.nombre, SUM(m.monto) AS total
            FROM movimientos m
            INNER JOIN categorias c ON m.id_categoria = c.id_categoria
            WHERE c.tipo = 'Gasto' AND m.id_usuario = ?
        """
        params = [uid]

        if mes:
            query += " AND FORMAT(m.fecha, 'yyyy-MM') = ?"
            params.append(mes)

        query += " GROUP BY c.nombre ORDER BY total ASC"

        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(query, *params)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.close()
        cn.close()
        return jsonify({"ok": True, "categorias": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── DELETE /movimientos/<id> ──────────────────────────────────────────────────
@app.route("/movimientos/<int:id>", methods=["DELETE"])
@token_requerido
def eliminar_movimiento(id):
    try:
        uid    = request.usuario_id
        cn     = conectar_sql()
        cursor = cn.cursor()
        # Solo elimina si el movimiento pertenece al usuario
        cursor.execute(
            "DELETE FROM movimientos WHERE id_movimiento = ? AND id_usuario = ?", id, uid
        )
        cn.commit()
        cursor.close()
        cn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── PUT /movimientos/<id> ─────────────────────────────────────────────────────
@app.route("/movimientos/<int:id>", methods=["PUT"])
@token_requerido
def editar_movimiento(id):
    try:
        uid    = request.usuario_id
        data   = request.get_json()
        cn     = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(
            """
            UPDATE movimientos
            SET fecha = ?, id_categoria = ?, descripcion = ?, monto = ?
            WHERE id_movimiento = ? AND id_usuario = ?
            """,
            data["fecha"], data["categoria"], data["descripcion"], data["monto"], id, uid
        )
        cn.commit()
        cursor.close()
        cn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── INICIO ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
