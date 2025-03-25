from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import timedelta

db = SQLAlchemy()


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
    operational_at = db.Column(db.DateTime, nullable=False)
    battery_capacity_wh = db.Column(db.Integer, nullable=False)
    size_watt = db.Column(db.Integer, nullable=False)

# Requires 5 API calls to populate each week (if battery is present)
# Free API is 10 calls/min or 1000 calls/month
#  This means: access 2 weeks/minute, access 200 weeks/month
class HistoricalData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign Key
    system_id = db.Column(db.Integer, db.ForeignKey('systemdetails.system_id'), nullable=True)
    timestamp_end = db.Column(db.DateTime, nullable=False)
    interval_len_sec = db.Column(db.Integer, nullable=False)
    production_wh = db.Column(db.Integer, nullable=False)
    consumption_wh = db.Column(db.Integer, nullable=False)
    import_wh = db.Column(db.Integer, nullable=False)
    export_wh = db.Column(db.Integer, nullable=False)
    batt_charge_wh = db.Column(db.Integer, nullable=False)
    batt_discharge_wh = db.Column(db.Integer, nullable=False)

    @hybrid_property
    def timestamp_start(self):
        """Calculated field: start time"""
        return self.timestamp_start - timedelta(seconds=self.interval_len_sec)

