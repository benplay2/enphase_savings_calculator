from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from db_models import db, User, SystemDetails, HistoricalData
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import json
import os
from datetime import datetime, timedelta
import pandas as pd

import enphase_api
import solar_sim

# import random  # Example: for simulation logic

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('ENPHASE_SAVINGS_CALCULATOR_SECRET')

if app.config['SECRET_KEY'] is None or len(app.config['SECRET_KEY']) == 0:
    raise ValueError("Environment variable 'ENPHASE_SAVINGS_CALCULATOR_SECRET' is not defined.")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

port = 5000

app.config["UPLOAD_FOLDER"] = "uploads"  # Directory to save uploaded files

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# db = SQLAlchemy(app)
db.init_app(app)  # Bind SQLAlchemy to the Flask app

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# def run_simulation(param):
#     # Example simulation: random number generation based on input
#     return {"result": random.randint(1, param)}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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

def get_populated_data_week_list(system_id:int):
    # Return a list of [datetime startday, boolean populated] for each week of 
    # fully populated data for the system specified
    #
    # The first entry will be day 1, 8, 15, 22, or 29 of the month
    # Get the current date
    now = datetime.now()

    # Create a datetime object for today at 12:00am
    two_yr_ago = datetime(now.year-2, now.month, now.day)
    two_yr_ago = adjust_datetime_to_weeks_after_first_day(two_yr_ago + timedelta(days=1))      
    
    system_details = SystemDetails.query.filter_by(system_id=system_id).first()

    install_time = system_details.operational_at
    install_day = adjust_datetime_to_weeks_after_first_day(install_time)
    
    first_entry = HistoricalData.query.filter_by(system_id=system_id).order_by(HistoricalData.timestamp_end).first()
    if first_entry is not None:
        first_downloaded_date = adjust_datetime_to_weeks_after_first_day(first_entry.timestamp_end)
    else:
        first_downloaded_date = now

    first_reported_day = two_yr_ago
    if first_downloaded_date < two_yr_ago:
        first_reported_day = first_downloaded_date
    if first_reported_day < install_day:
        first_reported_day = install_day

    final_week = adjust_datetime_to_weeks_after_first_day_neg(now)

    week_list = []
    cur_day = first_reported_day
    while cur_day <= final_week:
        if cur_day.day % 7 == 1:
            week_list.append([cur_day, False])
        cur_day = adjust_datetime_to_weeks_after_first_day(cur_day + timedelta(days=1))
        
    fifteenMin = timedelta(minutes=15)
    for index, week_entry in enumerate(week_list):
        if index < len(week_list) - 1:
            stop_day = week_list[index+1][0] #day to stop before (non-inclusive)
        else:
            stop_day = datetime(now.year, now.month, now.day+1)

        cur_start_day = week_entry[0]
        cur_data_entries = HistoricalData.query.filter( (HistoricalData.system_id==system_id) & 
                                                          (HistoricalData.timestamp_end > cur_start_day) & 
                                                          (HistoricalData.timestamp_end <= stop_day)).order_by(HistoricalData.timestamp_end).all()
        if cur_data_entries is None or len(cur_data_entries) == 0:
            continue
        elif (cur_data_entries[0].timestamp_end - cur_start_day) > fifteenMin + timedelta(minutes=1):
            continue
        elif (stop_day - cur_data_entries[-1].timestamp_end) > timedelta(minutes=1):
            continue

        # If there are any periods of > 15min without data, the answer is "False"
        prev_time = cur_start_day + timedelta(minutes=1)
        all_data_present = True
        for cur_entry in cur_data_entries:
            cur_time = cur_entry.timestamp_end
            if cur_time - prev_time > fifteenMin:
                all_data_present = False
                break
            prev_time = cur_time
        if all_data_present:
            week_list[index][1] = True

    return week_list

def adjust_datetime_to_weeks_after_first_day(datetime_in):
    datetime_out = datetime(datetime_in.year, datetime_in.month, datetime_in.day)
    day_diff = (datetime_out.day % 7) - 1
    if day_diff > 0:
        datetime_out = datetime_out + timedelta(days=(7-day_diff))
        if datetime_out.day > 1 and datetime_out.day < 8:
            datetime_out = datetime(datetime_out.year, datetime_out.month, 1)
    return datetime_out

def adjust_datetime_to_weeks_after_first_day_neg(datetime_in):
    adj_datetime = adjust_datetime_to_weeks_after_first_day(datetime_in=datetime_in)
    if adj_datetime > datetime_in:
        adj_datetime = adjust_datetime_to_weeks_after_first_day(adj_datetime - timedelta(days=7))
    return adj_datetime

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
            return redirect(url_for('dashboard', refresh=True))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html',)

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
    refresh_systems = request.args.get('refresh',False,type=bool)
    if current_user.refresh_token is None:
        auth_url = enphase_api.get_initialize_auth_url(redirect_uri=get_token_dict(current_user)['redirect_uri'])
        return redirect(auth_url)

    existing_detail = db.session.query(SystemDetails).filter_by(user_id=current_user.id).first()

    if refresh_systems or existing_detail is None:
        token_dict, system_dict_list = enphase_api.get_all_system_summaries(token_dictionary=get_token_dict(current_user))
        update_user_token_info(current_user, token_dict)

        # Update SystemDetails database to hold system_dict
        if len(system_dict_list) > 0:
            #Add new entries or update existing
            for detail in system_dict_list:
                existing_detail = SystemDetails.query.filter((SystemDetails.user_id==current_user.id) & (SystemDetails.system_id==detail['system_id'])).first()
                if existing_detail:
                    existing_detail.num_modules=detail['modules']
                    existing_detail.battery_capacity_wh=detail['battery_capacity_wh']
                    existing_detail.size_watt=detail['size_w']
                    existing_detail.operational_at=datetime.fromtimestamp(detail['operational_at'])
                else:
                    new_details_entry = SystemDetails(user_id=current_user.id, 
                                                system_id=detail['system_id'],
                                                name=detail['name'],
                                                num_modules=detail['modules'],
                                                battery_capacity_wh=detail['battery_capacity_wh'],
                                                size_watt=detail['size_w'],
                                                operational_at=datetime.fromtimestamp(detail['operational_at']))
                    db.session.add(new_details_entry)
            
            db.session.commit()
    system_detail_entries = SystemDetails.query.filter_by(user_id=current_user.id).all()

    return render_template("dashboard.html", username=current_user.username, system_detail_entries=system_detail_entries)

@app.route('/system')
@login_required
def system_details():
    system_id = request.args.get('id', None, type=int)
    if system_id is None:
        return "{\"Error\":\"id was not specified}", 400

    week_populated_list = get_populated_data_week_list(system_id=system_id)

    return render_template("system_details.html", system_dict=SystemDetails.query.filter_by(system_id=system_id).first(),
                           week_populated_list=week_populated_list, system_id=system_id)

@app.route('/upload_enphase_energy_report', methods=["POST"])
@login_required
def upload_report_csv():
    system_id = request.args.get('system_id', None, type=int)
    if system_id is None:
        return "{\"Error\":\"system_id was not specified}", 400
    
    if "file" not in request.files:
        flash("No file selected!")
        return redirect(url_for("system_details", id=system_id))

    file = request.files["file"]

    if file.filename == "":
        flash("No selected file!")
        return redirect(url_for("system_details", id=system_id))

    if file and file.filename.endswith(".csv"):
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)  # Save file

        # Optional: Process CSV using pandas
        df = pd.read_csv(filepath, usecols=["Date/Time"])
        first_time_start = datetime.strptime(df["Date/Time"].values[0], "%Y-%m-%d %H:%M:%S %z")
        second_time_start = datetime.strptime(df["Date/Time"].values[1], "%Y-%m-%d %H:%M:%S %z")
        csv_time_interval_len = second_time_start - first_time_start

        last_time_end = datetime.strptime(df["Date/Time"].values[-1], "%Y-%m-%d %H:%M:%S %z") + csv_time_interval_len

        #Delete any existing entries between first and last time
        db.session.query(HistoricalData).filter((HistoricalData.system_id==system_id)
                                                   & (HistoricalData.timestamp_end >= first_time_start+csv_time_interval_len-timedelta(minutes=3))
                                                   & (HistoricalData.timestamp_end <= last_time_end+timedelta(minutes=3))).delete()

        for chunk in pd.read_csv(filepath, chunksize=1):        
            cur_time_start = datetime.strptime(chunk["Date/Time"].values[0], "%Y-%m-%d %H:%M:%S %z")
            cur_time_end = cur_time_start + csv_time_interval_len

            #TODO: Detect if battery charge/discharge is in the CSV (I don't know the column name..)
            batt_charge_wh = 0
            batt_discharge_wh = 0

            new_entry = HistoricalData(user_id=current_user.id,system_id=system_id,
                                    timestamp_end=cur_time_end,
                                    interval_len_sec=csv_time_interval_len.seconds,
                                    production_wh=chunk["Energy Produced (Wh)"].values[0],
                                    consumption_wh=chunk["Energy Consumed (Wh)"].values[0],
                                    import_wh=chunk["Imported from Grid (Wh)"].values[0],
                                    export_wh=chunk["Exported to Grid (Wh)"].values[0],
                                    batt_charge_wh=batt_charge_wh,
                                    batt_discharge_wh=batt_discharge_wh)
            db.session.add(new_entry)
            
        db.session.commit()


        flash("Processed the CSV")
        return redirect(url_for("system_details", id=system_id))

    flash("Invalid file format. Please upload a CSV file.")
    return redirect(url_for("system_details", id=system_id))

@app.route('/fetchdata_week',methods=['GET'])
@login_required
def fetchdata_week():
    start_at = request.args.get('start_at', None, type=int)
    system_id = request.args.get('system_id', None, type=int)
    if start_at is None:
        return "{\"Error\":\"start_at was not specified}", 400
    if system_id is None:
        return "{\"Error\":\"system_id was not specified}", 400

    # Get data starting at start_at, every 15 minutes (week)
    # Populate the database with this information (production, consumption, battery usage, etc.)

    cur_system = SystemDetails.query.filter((SystemDetails.system_id==system_id) & (SystemDetails.user_id==current_user.id)).first()
    if cur_system is None:
        return "{\"Error\":\"system_id not found!}", 404
    
    batt_present = cur_system.battery_capacity_wh > 0
    token_dict = current_user.access_token
    token_dict, prod_telemetry = enphase_api.get_production_telemetry(token_dictionary=get_token_dict(current_user), system_id=cur_system.system_id, start_at=start_at)
    token_dict, cons_telemetry = enphase_api.get_consumption_telemetry(token_dictionary=get_token_dict(current_user), system_id=cur_system.system_id, start_at=start_at)
    token_dict, export_telemetry = enphase_api.get_energy_export_telemetry(token_dictionary=get_token_dict(current_user), system_id=cur_system.system_id, start_at=start_at)
    token_dict, import_telemetry = enphase_api.get_energy_import_telemetry(token_dictionary=get_token_dict(current_user), system_id=cur_system.system_id, start_at=start_at)

    if batt_present:
        token_dict, batt_telemetry = enphase_api.get_battery_telemetry(token_dictionary=get_token_dict(current_user), system_id=cur_system.system_id, start_at=start_at)
    else:
        batt_telemetry = None

    update_user_token_info(current_user, token_dict)

    prod_intervals = prod_telemetry['intervals']
    cons_intervals = cons_telemetry['intervals']
    export_intervals = export_telemetry['intervals'] #Outer list element for each day
    #Flatten
    export_intervals = [item for sublist in export_intervals for item in sublist]
    import_intervals = import_telemetry['intervals'] #Outer list element for each day
    #Flatten
    import_intervals = [item for sublist in import_intervals for item in sublist]
    if batt_telemetry is None:
        batt_intervals = None
    else:
        batt_intervals = batt_telemetry['intervals']

    first_time = datetime.fromtimestamp(prod_intervals[0]['end_at'])
    last_time = datetime.fromtimestamp(prod_intervals[-1]['end_at'])
    interval_len = datetime.fromtimestamp(prod_intervals[1]['end_at']) - first_time

    #Delete existing entries
    db.session.query(HistoricalData).filter((HistoricalData.system_id==system_id)
                                                   & (HistoricalData.timestamp_end >= first_time)
                                                   & (HistoricalData.timestamp_end <= last_time)).delete()

    #Go through "intervals". Each telemetry output should have the same intervals.
    #Delete any existing data between intervals[0].end_at and intervals[-1].end_at
    for i in range(0, len(prod_intervals)):
        if batt_present:
            batt_charge_wh = batt_intervals[i]['charge']['enwh']
            batt_discharge_wh = batt_intervals[i]['discharge']['enwh']
        else:
            batt_charge_wh = 0
            batt_discharge_wh = 0
        new_entry = HistoricalData(user_id=current_user.id,system_id=system_id,
                                   timestamp_end=datetime.fromtimestamp(prod_intervals[i]['end_at']),
                                   interval_len_sec=interval_len.seconds,
                                   production_wh=prod_intervals[i]['wh_del'],
                                   consumption_wh=cons_intervals[i]['enwh'],
                                   import_wh=import_intervals[i]['wh_imported'],
                                   export_wh=export_intervals[i]['wh_exported'],
                                   batt_charge_wh=batt_charge_wh,
                                   batt_discharge_wh=batt_discharge_wh)
        db.session.add(new_entry)
            
    db.session.commit()

    #Populate new entries and commit

    return "{\"Result\":\"Success!\"}", 200

@app.route("/simulation", methods=["GET", "POST"])
@login_required
def simulate():
    system_id = request.form.get('system_id', None, type=int)
    if system_id is None:
        system_id = request.args.get('system_id', None, type=int)
        if system_id is None:
            return "{\"Error\":\"system_id was not specified}", 400

    sys_details = db.session.query(SystemDetails).filter((SystemDetails.system_id == system_id) &
                                           (SystemDetails.user_id == current_user.id)).first()
    if request.method == "POST":
        # Get submitted form values
        data = request.form.to_dict()

        #TODO: actually populate these with "data"
        solar_array = solar_sim.SolarArray
        battery = solar_sim.SolarBattery
        grid = solar_sim.Grid

        target_data = db.session.query(HistoricalData).filter((SystemDetails.system_id == system_id) &
                                           (SystemDetails.user_id == current_user.id)).all()

        controller = solar_sim.SimController(panels=solar_array, battery=battery, grid=grid)
        sim_out = controller.simulate(target_data, sys_details.num_modules)

        # (Here, you'd process the data and run your simulation)
        results = "Simulation complete. Results: ..."  # Placeholder
        return render_template("simulation_form.html", results=results, **data)
    
    
    
    week_populated_list = get_populated_data_week_list(system_id=system_id)
    
    start_datetime = None
    end_datetime = None
    if len(week_populated_list) > 0:
        # Loop through week populated list to pull out the extents of when data was populated
        for wk_data in week_populated_list:
            #wk_data = [datetime, boolean]
            if wk_data[1]:
                start_datetime = wk_data[0]
                break

        for wk_data in reversed(week_populated_list):
            #wk_data = [datetime, boolean]
            if wk_data[1]:
                end_datetime = wk_data[0] + timedelta(days=7)
                break
    
    if start_datetime is None:
        formatted_start = ""
        formatted_end = ""
    else:
        formatted_start = start_datetime.strftime("%Y-%m-%dT%H:%M")
        formatted_end = end_datetime.strftime("%Y-%m-%dT%H:%M")

    # Default initial values
    initial_values = {
        "system_id": system_id,
        "system_name": sys_details.name,
        "module_count": sys_details.num_modules,
        "batt_usable_energy_kwh": sys_details.battery_capacity_wh/1000,
        "batt_charge_eff": 0.9,
        "batt_discharge_eff": 0.9,
        "batt_max_c_rate": 3.0,
        "grid_weekday_on_peak_start": "15:00",
        "grid_weekday_on_peak_end": "19:00",
        "grid_weekend_on_peak_start": "00:00",
        "grid_weekend_on_peak_end": "00:00",
        "grid_weekday_off_peak_cost_per_kwh": 0.17885,
        "grid_weekday_on_peak_cost_per_kwh": 0.19374,
        "grid_weekend_off_peak_cost_per_kwh": 0.17885,
        "grid_weekend_on_peak_cost_per_kwh": 0.17885,

        "grid_weekday_off_peak_gen_pay_per_kwh":0.08978,
        "grid_weekday_on_peak_gen_pay_per_kwh":0.10467,
        "grid_weekday_off_peak_creditable_per_kwh":0.17885,
        "grid_weekday_on_peak_creditable_per_kwh":0.19374,

        "grid_weekend_off_peak_gen_pay_per_kwh":0.08978,
        "grid_weekend_on_peak_gen_pay_per_kwh":0.08978,
        "grid_weekend_off_peak_creditable_per_kwh":0.17885,
        "grid_weekend_on_peak_creditable_per_kwh":0.17885,
        "start_datetime": formatted_start,
        "end_datetime": formatted_end
    }

    return render_template("simulation_form.html", results=None, **initial_values)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))




# Old simulate example
# @app.route('/simulate', methods=['POST'])
# def simulate():
#     data = request.json
#     param = data.get("param", 10)
#     result = run_simulation(param)
#     return jsonify(result)

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
        # db.drop_all()
        db.create_all()  # Create database tables
    app.run(debug=True, port=5000)
