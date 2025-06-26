from flask import (
    Blueprint,
    session,
    render_template,
    redirect,
    url_for,
    send_file,
)
from flask import current_app as app
import json
import os
from db import get_connection


estimate_blueprint = Blueprint('estimate', __name__)


@estimate_blueprint.route('/history', endpoint='history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS excel_history (
                   id INT AUTO_INCREMENT PRIMARY KEY,
                   user_id INT NOT NULL,
                   filename VARCHAR(255) NOT NULL,
                   data_json TEXT,
                   created_at DATETIME DEFAULT CURRENT_TIMESTAMP
               )'''
        )
        cursor.execute(
            'SELECT id, filename, data_json, created_at FROM excel_history WHERE user_id=%s ORDER BY created_at DESC',
            (user_id,)
        )
        history_list = cursor.fetchall()
    conn.close()

    for row in history_list:
        try:
            row['data'] = json.loads(row.get('data_json', '{}'))
            except Exception:
                row['data'] = {}
    return render_template('history.html', history_list=history_list)


@estimate_blueprint.route('/download/<int:file_id>', endpoint='download_excel')
def download_excel(file_id: int):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT filename FROM excel_history WHERE id=%s AND user_id=%s',
            (file_id, user_id)
        )
        row = cursor.fetchone()
    conn.close()
    if not row:
        return 'ファイルが見つかりません。'
    filepath = os.path.join(app.root_path, 'exports', str(user_id), row['filename'])
    if not os.path.exists(filepath):
        return 'ファイルが見つかりません。'
    return send_file(
        filepath,
        as_attachment=True,
        download_name=row['filename'],
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
