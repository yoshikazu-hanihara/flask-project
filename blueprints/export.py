# blueprints/export.py
from flask import Blueprint, session, send_file, redirect, url_for, flash
from flask import current_app as app
from flask_mail import Message
from io import BytesIO
import os, datetime
import openpyxl

export_bp = Blueprint("export", __name__, url_prefix="/export")

# ─────────────────────────────────────────
# 1. テンプレートのパス  
#    static/template/estimate_template.xlsx という想定
# ─────────────────────────────────────────
TPL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # flask-project/
    "static", "template", "estimate_template.xlsx"
)

# ─────────────────────────────────────────
# 2. Python のキー → テンプレ内セル の対応表
#    （※セル番地はテンプレに合わせて自由に編集）
# ─────────────────────────────────────────
CELL_MAP = {
    "sales_price":             "C12",
    "order_quantity":          "C13",
    "product_weight":          "C14",
    "mold_unit_price":         "C15",
    "mold_count":              "C16",
    "raw_material_cost_total": "F20",
    "manufacturing_cost_total":"F21",
    "sales_admin_cost_total":  "F22",
    "profit_amount":           "F24",
    "profit_amount_total":     "F25",
    "profit_ratio":            "F26",
}

# - - - - - - - - - - - - - - - - - - - - -
def _build_workbook(data: dict) -> BytesIO:
    """
    テンプレートを読み込み、指定セルに値を差し込み、
    メモリ上 (BytesIO) に保存して返す。
    """
    # ❶ テンプレート読み込み（書式・画像・罫線保持）
    wb = openpyxl.load_workbook(TPL_PATH)
    ws = wb.active          # 見積書シートは1枚目想定

    # ❷ セルに値を流し込む
    for key, cell in CELL_MAP.items():
        if key in data:
            ws[cell].value = data[key]

    # ❸ 発行日（例）: テンプレ側で日付セルを用意しているなら
    ws["H3"].value = datetime.date.today().strftime("%Y/%m/%d")

    # ❹ シート側数式を再計算させる場合
    wb.calculation_properties.fullCalcOnLoad = True

    # ❺ メモリに保存
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio
# - - - - - - - - - - - - - - - - - - - - -

def _make_filename() -> str:
    return f"見積書_{datetime.datetime.now():%Y%m%d_%H%M%S}.xlsx"

@export_bp.route("/excel")
def download_excel():
    data = session.get("dashboard_data")
    if not data:
        flash("先に見積りを計算してください。")
        return redirect(url_for("dashboard.dashboard"))

    bio = _build_workbook(data)
    filename = _make_filename()

    # バックアップ保存（任意）
    export_dir = os.path.join(app.root_path, "exports")
    os.makedirs(export_dir, exist_ok=True)
    with open(os.path.join(export_dir, filename), "wb") as f:
        f.write(bio.getbuffer())

    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@export_bp.route("/mail")
def mail_excel():
    data = session.get("dashboard_data")
    if not data:
        flash("先に見積りを計算してください。")
        return redirect(url_for("dashboard.dashboard"))

    try:
        bio = _build_workbook(data)
        filename = _make_filename()

        msg = Message(
            subject="新しい見積書",
            recipients=["nworks12345@gmail.com"],       # ←宛先を必要に応じて変更
            body="自動生成した見積書 Excel を添付します。"
        )
        msg.attach(
            filename,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            bio.getvalue()
        )
        app.extensions["mail"].send(msg)
        flash("メールを送信しました。")
    except Exception as e:
        app.logger.exception("mail_excel failed")
        flash(f"メール送信に失敗しました: {e}")

    return redirect(url_for("dashboard.dashboard"))
