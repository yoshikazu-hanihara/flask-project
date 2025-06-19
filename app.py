# app.py  ―― メール機能を除去した最小構成
from flask import Flask, render_template

# 各種 Blueprint をインポート
from blueprints.dashboard import dashboard_bp
from blueprints.auth import auth
from estimate import estimate_blueprint
from blueprints.export import export_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'      # セッション用シークレット

# Blueprint 登録
app.register_blueprint(auth, url_prefix='')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(estimate_blueprint, url_prefix='/estimate')
app.register_blueprint(export_bp)

@app.route('/')
def index():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
