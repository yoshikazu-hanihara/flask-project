from flask import Blueprint, session, send_file, redirect, url_for, flash
from flask import current_app as app
from flask_mail import Message
from io import BytesIO
import os, datetime
import openpyxl

export_bp = Blueprint('export', __name__, url_prefix='/export')

def _build_workbook(data: dict) -> BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Estimate"

    # 見出しと値を 2 列でざっくり書く例
    for row_idx, (k, v) in enumerate(data.items(), start=1):
        ws.cell(row=row_idx, column=1, value=k)
        ws.cell(row=row_idx, column=2, value=v)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio

@export_bp.route('/excel')
def download_excel():
    data = session.get('dashboard_data')
    if not data:
        flash("先に見積りを計算してください。")
        return redirect(url_for('dashboard.dashboard'))

    bio = _build_workbook(data)
    filename = f"estimate_{datetime.datetime.now():%Y%m%d_%H%M%S}.xlsx"

    # ローカルにも保存する（バックアップしたい場合）
    save_path = os.path.join(app.root_path, 'exports', filename)
    with open(save_path, 'wb') as f:
        f.write(bio.getbuffer())

    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@export_bp.route('/mail')
def mail_excel():
    try:
        data = session.get('dashboard_data')
        if not data:
            flash("先に見積りを計算してください。")
            return redirect(url_for('dashboard.dashboard'))

        bio = _build_workbook(data)
        filename = f"estimate_{datetime.datetime.now():%Y%m%d_%H%M%S}.xlsx"

        msg = Message(
            subject="新しい見積もりデータ",
            recipients=["nworks12345@gmail.com"],
            body="自動生成された見積もり Excel を添付します。"
        )
        msg.attach(
            filename,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            bio.getvalue()
        )

        current_app.extensions["mail"].send(msg)
        flash("メールを送信しました。")
    except Exception as e:
        current_app.logger.exception("mail_excel failed")
        flash(f"メール送信に失敗しました: {e}")
    return redirect(url_for('dashboard.dashboard'))
