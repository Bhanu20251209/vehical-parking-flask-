from flask import Flask
from flask_login import LoginManager
import os
from models.models import *


login_manager = LoginManager()
login_manager.login_view = 'auth.login'


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 

db.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from controllers.auth_routes import auth_bp
from controllers.admin_routes import admin_bp
from controllers.user_routes import user_bp



app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(email='admin@admin.com', password='admin', role='admin')
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True,port=5500,host='0.0.0.0')
