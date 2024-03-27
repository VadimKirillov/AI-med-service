from flask import Flask, render_template, request
from models.scratch import CovidClassifier
from models.classifier import classify_image
from werkzeug.utils import secure_filename
from datetime import datetime
import torch
import os
import psycopg2
from psycopg2 import sql

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'static/images'
# Разрешенные типы файлов
ALLOWED_EXTENSIONS = {'png', 'jpg'}

# Настройки для подключения к базе данных PostgreSQL
DB_NAME = ''
DB_USER = ''
DB_PASSWORD = ''
DB_HOST = ''
DB_PORT = ''


# Функция для установления соединения с базой данных
def connect_to_db():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    return conn


# Функция для создания таблицы, если она ещё не существует
def create_table():
    conn = connect_to_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detection_logs (
            id SERIAL PRIMARY KEY,
            status VARCHAR,
            process_time TIMESTAMP,
            author VARCHAR
        )
    """)
    conn.commit()
    conn.close()


create_table()


# Функция для записи данных о детекции в базу данных
def log_detection(status, process_time, author):
    conn = connect_to_db()
    cur = conn.cursor()
    cur.execute(
        sql.SQL("INSERT INTO detection_logs (status, process_time, author) VALUES (%s, %s, %s)"),
        (status, process_time, author)
    )
    conn.commit()
    conn.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def base():
    return render_template("base.html")


@app.route("/detect", methods=['GET', 'POST'])
def page1():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template("detect.html", error="No file part")

        file = request.files['file']

        if file.filename == '':
            return render_template("detect.html", error="No selected file")

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            model = CovidClassifier()
            model.load_state_dict(torch.load('static/covid_classifier_weights.pth'))

            start_time = datetime.now().isoformat()
            predicted_label = classify_image(file_path, model)[0]
            predicted_prob = classify_image(file_path, model)[1]

            print(predicted_label)


            image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
            image_path = os.path.join('static/images', image_filename)
            end_time = datetime.now().isoformat()

            log_detection("Обработано", end_time, 'demo_user')

            return render_template("detect.html", predicted_label=predicted_label, predicted_prob=predicted_prob,
                                   image_path=image_path,
                                   start_time=start_time, end_time=end_time)

    return render_template("detect.html")


@app.route("/logs")
def page2():
    conn = connect_to_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM detection_logs")
    detection_logs = cur.fetchall()
    conn.close()
    return render_template("logs.html", detection_logs=detection_logs)


@app.route("/info")
def page3():
    return render_template("info.html")


if __name__ == "__main__":
    app.run(debug=True)
