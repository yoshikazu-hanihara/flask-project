# blueprints/preset.py
from flask import Blueprint, jsonify, session
import json
from db import get_connection

preset_bp = Blueprint("preset", __name__, url_prefix="/dashboard")

@preset_bp.route("/presets")
def list_presets():
    """
    自分の最新10件の見積もりをプリセット候補として返す。
    未ログイン時は空配列。
    返り値:
      [
        {"id": 17, "name": "¥380 / 1 000個", "data": {...入力フィールド名と値...}},
        ...
      ]
    """
    if "user_id" not in session:
        return jsonify([])

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, estimate_data
            FROM estimates
            WHERE user_id=%s AND status='active'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (session["user_id"],),
        )
        rows = cur.fetchall()
    conn.close()

    presets = []
    for r in rows:
        d = json.loads(r["estimate_data"])
        presets.append(
            {
                "id": r["id"],
                "name": f"¥{int(d['sales_price']):,} / {int(d['order_quantity']):,}個",
                # HTML の <input name="..."> と同じキーだけに絞る
                "data": {
                    "sales_price":        d.get("sales_price", ""),
                    "order_quantity":     d.get("order_quantity", ""),
                    "product_weight":     d.get("product_weight", ""),
                    "mold_unit_price":    d.get("mold_unit_price", ""),
                    "mold_count":         d.get("mold_count", ""),
                    "glaze_cost":         d.get("glaze_cost", ""),
                    "poly_count":         d.get("poly_count", ""),
                    "kiln_count":         d.get("kiln_count", ""),
                    "gas_unit_price":     d.get("gas_unit_price", ""),
                    "loss_defective":     d.get("loss_defective", ""),
                },
            }
        )
    return jsonify(presets)
