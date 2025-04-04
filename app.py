from flask import Flask, render_template
from flask_mail import Mail
from blueprints.dashboard import dashboard_bp
from blueprints.auth import auth_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

# Blueprintを登録
app.register_blueprint(auth_bp, url_prefix='')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

@app.route('/')
def index():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
