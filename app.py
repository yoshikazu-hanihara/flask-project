from flask import Flask, render_template
from flask_mail import Mail
from blueprints.dashboard import dashboard_bp
from blueprints.auth import auth
from estimate import estimate_blueprint
from blueprints.export import export_bp
from blueprints.preset import preset_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nworks12345@gmail.com'
app.config['MAIL_PASSWORD'] = 'yspr vktd yrmc wntn'
app.config['MAIL_DEFAULT_SENDER'] = 'nworks12345@gmail.com'
mail = Mail(app)

app.register_blueprint(auth, url_prefix='')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(estimate_blueprint, url_prefix='/estimate')
app.register_blueprint(export_bp)
app.register_blueprint(preset_bp)

@app.route('/')
def index():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
