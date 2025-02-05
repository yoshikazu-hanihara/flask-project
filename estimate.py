# estimate.py

from flask import Blueprint, request, session, render_template, redirect, url_for
import json
from db import get_connection

# Blueprintの生成
# 第1引数: Blueprint名 = 'estimate'
# 第2引数: モジュール名 = __name__
estimate_blueprint = Blueprint('estimate', __name__)

# ※ app.pyで使用していた _cleanup_deleted 関数もこちらへ移動します
def cleanup_deleted(user_id, cursor):
    cursor.execute("SELECT COUNT(*) as cnt FROM estimates WHERE user_id=%s AND status='deleted'", (user_id,))
    del_count = cursor.fetchone()['cnt']
    if del_count > 30:
        cursor.execute("""
          SELECT id FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at ASC LIMIT 1
        """, (user_id,))
        oldest = cursor.fetchone()
        if oldest:
            cursor.execute("DELETE FROM estimates WHERE id=%s", (oldest['id'],))


# (1) 履歴一覧
@estimate_blueprint.route('/history', endpoint='history')  # endpointを 'history' に
def history():
    if 'user_id' not in session:
        # auth側のlogin(エンドポイント = 'auth.login') へリダイレクト
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        # アクティブ一覧
        cursor.execute("""
          SELECT id, estimate_data, created_at 
            FROM estimates
           WHERE user_id=%s AND status='active'
           ORDER BY created_at DESC
        """, (user_id,))
        active_list = cursor.fetchall()
        for row in active_list:
            row['estimate_data'] = json.loads(row['estimate_data'])

        # 削除済み一覧
        cursor.execute("""
          SELECT id, estimate_data, created_at, deleted_at
            FROM estimates
           WHERE user_id=%s AND status='deleted'
           ORDER BY deleted_at DESC
        """, (user_id,))
        deleted_list = cursor.fetchall()
        for row in deleted_list:
            row['estimate_data'] = json.loads(row['estimate_data'])

        # 送信済み一覧
        cursor.execute("""
          SELECT id, estimate_data, created_at, sent_at
            FROM estimates
           WHERE user_id=%s AND status='sent'
           ORDER BY sent_at DESC
        """, (user_id,))
        sent_list = cursor.fetchall()
        for row in sent_list:
            row['estimate_data'] = json.loads(row['estimate_data'])
    conn.close()

    return render_template('history.html',
                           active_list=active_list,
                           deleted_list=deleted_list,
                           sent_list=sent_list)


# (2) 見積もりを「送信(最終確認)画面」にセットして移動
@estimate_blueprint.route('/send_estimate/<int:estid>', endpoint='send_estimate')
def send_estimate(estid):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))  # auth の login へ

    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          SELECT estimate_data 
            FROM estimates
           WHERE id=%s AND user_id=%s AND status='active'
        """, (estid, user_id))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return "この見積もりは存在しないか、既に削除または送信済みです。"

    # セッションへ再保存し、final_contact へ飛ばす
    data = json.loads(row['estimate_data'])
    session['estimate_id'] = estid
    session['dashboard_data'] = data
    return redirect(url_for('final_contact'))


# (3) 見積もり削除
@estimate_blueprint.route('/delete_estimate/<int:estid>', endpoint='delete_estimate')
def delete_estimate(estid):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          UPDATE estimates SET status='deleted', deleted_at=NOW()
           WHERE id=%s AND user_id=%s
        """, (estid, user_id))
        # 削除済みデータのクリーンアップ
        cleanup_deleted(user_id, cursor)
    conn.commit()
    conn.close()

    # endpoint='history' にしてあるので、url_for('history') が利用できる
    return redirect(url_for('history'))


# (4) 削除済みのPDFダミー表示
@estimate_blueprint.route('/pdf_only/<int:estid>', endpoint='pdf_only')
def pdf_only(estid):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
          SELECT estimate_data, status FROM estimates
           WHERE id=%s AND user_id=%s
        """, (estid, user_id))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return "見積もりが見つかりません。"
    if row['status'] != 'deleted':
        return "これは削除済みではありません。"

    data = json.loads(row['estimate_data'])
    price = data.get('total_cost', 0)
    return f"<h2>削除済み見積もり (PDFダミー)</h2><p>合計金額: {price} 円</p><p><a href='/history'>戻る</a></p>"
