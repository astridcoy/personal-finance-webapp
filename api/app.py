from flask import Flask, request, jsonify
from flask_cors import CORS
import pyodbc

app = Flask(__name__)
CORS(app)

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=FinanzasPersonales;"
    "Trusted_Connection=yes;"
)


def conectar_sql():
    return pyodbc.connect(CONNECTION_STRING)


# ── POST /guardar ─────────────────────────────────────────────────────────────
@app.route("/guardar", methods=["POST"])
def guardar():
    try:
        data = request.get_json()
        cn = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(
            "INSERT INTO movimientos (fecha, id_categoria, descripcion, monto) VALUES (?, ?, ?, ?)",
            data["fecha"], data["categoria"], data["descripcion"], data["monto"]
        )
        cn.commit()
        cursor.close()
        cn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GET /resumen ──────────────────────────────────────────────────────────────
@app.route("/resumen", methods=["GET"])
def resumen():
    try:
        cn = conectar_sql()
        cursor = cn.cursor()
        cursor.execute("""
            SELECT
                SUM(CASE WHEN c.tipo = 'Ingreso' THEN m.monto ELSE 0 END),
                SUM(CASE WHEN c.tipo = 'Gasto'   THEN m.monto ELSE 0 END)
            FROM movimientos m
            INNER JOIN categorias c ON m.id_categoria = c.id_categoria
        """)
        row = cursor.fetchone()
        cursor.close()
        cn.close()
        ingresos = float(row[0]) if row[0] else 0.0
        gastos   = float(row[1]) if row[1] else 0.0
        return jsonify({"ok": True, "ingresos": ingresos, "gastos": gastos, "balance": ingresos + gastos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── GET /movimientos ──────────────────────────────────────────────────────────
@app.route("/movimientos", methods=["GET"])
def movimientos():
    try:
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
            WHERE 1=1
        """
        params = []

        if mes:
            query += " AND FORMAT(m.fecha, 'yyyy-MM') = ?"
            params.append(mes)
        if categoria:
            query += " AND m.id_categoria = ?"
            params.append(int(categoria))

        query += " ORDER BY m.id_movimiento DESC"

        cn = conectar_sql()
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
def resumen_categorias():
    try:
        mes = request.args.get("mes")

        query = """
            SELECT c.nombre, SUM(m.monto) AS total
            FROM movimientos m
            INNER JOIN categorias c ON m.id_categoria = c.id_categoria
            WHERE c.tipo = 'Gasto'
        """
        params = []

        if mes:
            query += " AND FORMAT(m.fecha, 'yyyy-MM') = ?"
            params.append(mes)

        query += " GROUP BY c.nombre ORDER BY total ASC"

        cn = conectar_sql()
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
def eliminar_movimiento(id):
    try:
        cn = conectar_sql()
        cursor = cn.cursor()
        cursor.execute("DELETE FROM movimientos WHERE id_movimiento = ?", id)
        cn.commit()
        cursor.close()
        cn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── PUT /movimientos/<id> ─────────────────────────────────────────────────────
@app.route("/movimientos/<int:id>", methods=["PUT"])
def editar_movimiento(id):
    try:
        data = request.get_json()
        cn = conectar_sql()
        cursor = cn.cursor()
        cursor.execute(
            """
            UPDATE movimientos
            SET fecha = ?, id_categoria = ?, descripcion = ?, monto = ?
            WHERE id_movimiento = ?
            """,
            data["fecha"], data["categoria"], data["descripcion"], data["monto"], id
        )
        cn.commit()
        cursor.close()
        cn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── GET /categorias ───────────────────────────────────────────────────────────
@app.route("/categorias", methods=["GET"])
def obtener_categorias():
    try:
        cn = conectar_sql()
        cursor = cn.cursor()

        cursor.execute("""
            SELECT id_categoria, nombre, tipo
            FROM categorias
            ORDER BY id_categoria
        """)

        categorias = []

        for row in cursor.fetchall():
            categorias.append({
                "id_categoria": row[0],
                "nombre": row[1],
                "tipo": row[2]
            })

        cursor.close()
        cn.close()

        return jsonify({
            "ok": True,
            "categorias": categorias
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
    
    
# ── INICIO ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5000, debug=True)