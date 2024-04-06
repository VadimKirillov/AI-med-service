from models import db
from sqlalchemy import inspect


def create_tables_if_not_exist():
    connection = db.engine.connect()
    inspector = inspect(connection)
    if not inspector.has_table('user') or \
            not inspector.has_table('detection_logs'):
        db.create_all()
        print("Таблицы созданы.")

