from flask import Flask
from flask_mail import Mail
import os
import json
from db import get_connection

# blueprint 読み込み
from blueprints.dashboard import dashboard as dashboard_blueprint

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# (例) Flask-Mail の設定
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

# Blueprint登録: blueprint名='dashboard'、URLプリフィックスは空にしている
app.register_blueprint(dashboard_blueprint, url_prefix='')

if __name__ == '__main__':
    app.run(debug=True)
