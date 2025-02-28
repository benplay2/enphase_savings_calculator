from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import os
from datetime import datetime

import enphase_api

import random  # Example: for simulation logic

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('ENPHASE_SAVINGS_CALCULATOR_SECRET')

if app.config['SECRET_KEY'] is None or len(app.config['SECRET_KEY']) == 0:
    raise ValueError("Environment variable 'ENPHASE_SAVINGS_CALCULATOR_SECRET' is not defined.")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

port = 5000


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def run_simulation(param):
    # Example simulation: random number generation based on input
    return {"result": random.randint(1, param)}

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    refresh_token = db.Column(db.String(1000), nullable=True)
    access_token = db.Column(db.String(1000), nullable=True)
    access_token_expiration = db.Column(db.DateTime, nullable=True)

# User-Specific data
class SystemDetails(db.Model):
    __tablename__ = 'systemdetails'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign Key
    system_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(500), nullable=True)
    num_modules = db.Column(db.Integer, nullable=False)
    battery_capacity_wh = db.Column(db.Integer, nullable=False)
    size_watt = db.Column(db.Integer, nullable=False)

# Requires 5 API calls to populate each week (if battery is present)
# Free API is 10 calls/min or 1000 calls/month
#  This means: access 2 weeks/minute, access 200 weeks/month
class HistoricalData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign Key
    system_id = db.Column(db.Integer, db.ForeignKey('systemdetails.system_id'), nullable=True)
    timestamp_start = db.Column(db.DateTime, nullable=False)
    interval_len_sec = db.Column(db.Integer, nullable=False)
    production_wh = db.Column(db.Integer, nullable=False)
    consumption_wh = db.Column(db.Integer, nullable=False)
    import_wh = db.Column(db.Integer, nullable=False)
    export_wh = db.Column(db.Integer, nullable=False)
    batt_charge_wh = db.Column(db.Integer, nullable=False)
    batt_discharge_wh = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Functions
def get_token_dict(user_entry) -> dict:
    token_dict = {
        'refresh_token': user_entry.refresh_token,
        'access_token': user_entry.access_token,
        'access_token_expiration': user_entry.access_token_expiration,
        'redirect_uri': f"http://localhost:{port}/enphase_auth" #Needs to be localhost because this isn't a world-accessible server
    }
    return token_dict

def update_user_token_info(user_entry, token_dict):
    user_entry.refresh_token = token_dict['refresh_token']
    user_entry.access_token = token_dict['access_token']
    user_entry.access_token_expiration = token_dict['access_token_expiration']
    db.session.commit() #save changes

# Routes

@app.route('/')
def home():
    return render_template('home.html')  # Load frontend

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    print(current_user.username)
    if current_user.refresh_token is None:
        auth_url = enphase_api.get_initialize_auth_url(redirect_uri=get_token_dict(current_user)['redirect_uri'])
        return redirect(auth_url)

    token_dict, system_dict_list = enphase_api.get_all_system_summaries(token_dictionary=get_token_dict(current_user))
    update_user_token_info(current_user, token_dict)

    # Update SystemDetails database to hold system_dict
    if len(system_dict_list) > 0:
        # Delete systems currently stored in the database
        existing_details = SystemDetails.query.filter_by(user_id=current_user.id).all()

        # Delete the entries
        for entry in existing_details:
            db.session.delete(entry)

        #Add new entries
        for detail in system_dict_list:
            new_details_entry = SystemDetails(user_id=current_user.id, 
                                              system_id=detail['system_id'],
                                              name=detail['name'],
                                              num_modules=detail['modules'],
                                              battery_capacity_wh=detail['battery_capacity_wh'],
                                              size_watt=detail['size_w'])
            db.session.add(new_details_entry)
        
        db.session.commit()

    return render_template("dashboard.html", username=current_user.username, system_dict_list=system_dict_list)

@app.route('/system')
@login_required
def system_details():
    system_id = request.args.get('id')

    #TODO: Get this from database
    week_populated_list = [
        [datetime(2025,2,1), True],
        [datetime(2025,2,8), True],
        [datetime(2025,2,15), False]
    ]

    return render_template("system_details.html", system_dict=SystemDetails.query.filter_by(system_id=system_id).first(),
                           week_populated_list=week_populated_list)

@app.route('/fetchdata_week',methods=['GET'])
@login_required
def fetchdata_week():
    start_at = request.args.get('start_at')

    return "{\"Result\":\"Not implemented yet!}", 501

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))





@app.route('/simulate', methods=['POST'])
def simulate():
    data = request.json
    param = data.get("param", 10)
    result = run_simulation(param)
    return jsonify(result)

@app.route('/reauthorize')
@login_required
def reauthorize():
    auth_url = enphase_api.get_initialize_auth_url(redirect_uri=get_token_dict(current_user)['redirect_uri'])
    return redirect(auth_url)

@app.route("/enphase_auth")
@login_required
def enphase_token():
    code = request.args.get('code')
    new_token_dict = enphase_api.authorize(code, token_dictionary=get_token_dict(current_user))
    update_user_token_info(current_user, new_token_dict)
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True, port=5000)
