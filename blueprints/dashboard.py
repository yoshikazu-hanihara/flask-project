from flask import Blueprint, render_template, request, jsonify, session, url_for, redirect
import json
from db import get_connection

# Blueprint名を 'dashboard' と指定
dashboard = Blueprint('dashboard', __name__)

# ------------------------------------
# もし定数や係数がある場合はここに
# ------------------------------------
DOHDAI_COEFFICIENT = 0.042
# ... (省略)


######################################
# 例: ダッシュボード表示用ルート
######################################
# 関数名も 'dashboard' にする → endpoint名='dashboard.dashboard'
@dashboard.route('/dashboard')
def dashboard():
    """
    ダッシュボード画面を表示
    """
    return render_template('dashboard.html')


######################################
# 例: POST処理
######################################
@dashboard.route('/dashboard_post', methods=['POST'])
def dashboard_post():
    """
    フォーム送信されて計算・結果表示する例
    """
    # 何らかの計算やDB処理
    # ...

    return render_template('dashboard_result.html')


######################################
# 例: 非同期計算API
######################################
@dashboard.route('/calculate', methods=['POST'])
def calculate():
    """
    AJAXなどで呼ばれる計算用API
    """
    return jsonify({"status": "ok"})


######################################
# (オマケ) dashboard へリダイレクト例
######################################
@dashboard.route('/redirect_to_dashboard')
def redirect_to_dashboard():
    """
    ここでdashboardへ飛ぶ → url_for('dashboard.dashboard')
    """
    # ここがポイント: 
    # ビュー関数名 = 'dashboard' 
    # Blueprint名   = 'dashboard'
    # よって endpoint名 は 'dashboard.dashboard'
    return redirect(url_for('dashboard.dashboard'))
