from models import db
from sqlalchemy import inspect


def create_tables_if_not_exist():
    connection = db.engine.connect()
    inspector = inspect(connection)
    if not inspector.has_table('user') or \
            not inspector.has_table('detection_logs') or \
            not inspector.has_table('modal') or \
            not inspector.has_table('target') or \
            not inspector.has_table('pathology') or \
            not inspector.has_table('service'):
        db.create_all()
        db.session.commit()
        print("Таблицы созданы.")

