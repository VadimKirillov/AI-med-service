from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import BYTEA

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), default='user')


class DetectionLogs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(100), nullable=False)
    name_patology = db.Column(db.String(100), nullable=False)
    percent_patology = db.Column(db.String(100), nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref='detection_logs')


# def create_tables_if_not_exist():
#     engine = db.engine()
#     if not engine.dialect.has_table(engine, 'user') or \
#             not engine.dialect.has_table(engine, 'detection_logs'):
#         db.create_all()
#         print("Таблицы созданы.")
