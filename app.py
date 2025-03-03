from flask import Flask
from flask_mail import Mail
import os
import json
from passlib.hash import bcrypt_sha256
from datetime import datetime

# DB接続用 (例: PyMySQL)
from db import get_connection

# 既存の他のBlueprint (auth, estimate) の読み込み
from auth import auth as auth_blueprint
from estimate import estimate_blueprint

# 今回新たに分割した dashboard.py (blueprints配下) の読み込み
from blueprints.dashboard import dashboard as dashboard_blueprint

######################################
# Flask基本設定
######################################
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用キー(例)

# Flask-Mail の設定 (例: Gmail)
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

# Blueprint の登録
app.register_blueprint(auth_blueprint, url_prefix='')
app.register_blueprint(estimate_blueprint, url_prefix='')

# 新しく分割したダッシュボード用Blueprint
app.register_blueprint(dashboard_blueprint, url_prefix='')


######################################
# メイン起動
######################################
if __name__ == '__main__':
    app.run(debug=True)
