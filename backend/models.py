from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(120), unique=True)

    username = db.Column(db.String(80))

    password = db.Column(db.String(255))

    role = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Input(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer)

    content_type = db.Column(db.String(50))

    content = db.Column(db.Text)

    file_path = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    input_id = db.Column(db.Integer)

    prediction = db.Column(db.String(20))

    confidence = db.Column(db.Float)

    manipulation_score = db.Column(db.Float)

    report_path = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)