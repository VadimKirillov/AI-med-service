from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
#from flask_mail import Mail, Message
from sqlalchemy import desc, select, and_
from nn_models.scratch import CovidClassifier
from nn_models.classifier import classify_image
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from access import group_permission_decorator
from database import *
from forms import *
from models import *
import json
import os
import random
import torch
import numpy as np
import psycopg2
from psycopg2 import sql
import pylibjpeg
import pydicom
from PIL import Image
import matplotlib.pyplot as plt

# Load DICOM file

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = '12345'

app.config['ACCESS_CONFIG'] = json.load(open('config/access.json', 'r'))
app.config['UPLOAD_FOLDER'] = 'static/images'

# Загрузка конфигурации из файла
with open('config/config.json', 'r') as f:
    config = json.load(f)

# Настройка подключения к базе данных
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}".format(
    **config)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация экземпляра SQLAlchemy
db.init_app(app)

# Создание таблиц, если они не существуют
if not os.path.exists("config/initialized"):
    with app.app_context():
        create_tables_if_not_exist()
        open("config/initialized", "w").close()

with app.app_context():
    if not Modal.query.all():
        # Добавление тестовых данных в таблицу Modal
        modal_data = ["КТ", "МРТ", "РГ", "ЭКГ", "Другое"]
        for modal_name in modal_data:
            modal = Modal(name=modal_name)
            db.session.add(modal)

    if not Target.query.all():
        # Добавление тестовых данных в таблицу Target
        target_data = ["Грудная полость", "Мозг", "Позвоночник", "Брюшная полость", "Мульти", "Другое"]
        for target_name in target_data:
            target = Target(name=target_name)
            db.session.add(target)

    if not Pathology.query.all():
        # Добавление тестовых данных в таблицу Pathology
        pathology_data = ["COVID-19", "Пневмония", "Опухоль", "Рак", "Другое"]
        for pathology_name in pathology_data:
            pathology = Pathology(name=pathology_name)
            db.session.add(pathology)

    if not User.query.all():
        admin = User(username='admin', password='admin', role='admin')
        user = User(username='user', password='user', role='user')

        db.session.add(admin)
        db.session.add(user)

    if not Service.query.all():
        covid_detector = Service(name='COVID-Classifier', url='covid_detector',
                                 description='COVID-19 бинарное определение',
                                 image_url='/static/images/covid_detector_logo.png',
                                 pathology_id=1, target_id=1, modal_id=3)

        covid_segmentator = Service(name='COVID-Segmentator', url='covid_segmentator',
                                    image_url='/static/images/covid_segmentator_logo.png',
                                    description='COVID-19 сегментация лёгких и поражённых областей',
                                    pathology_id=1, target_id=1, modal_id=3)

        brain_tumor_classifier = Service(name='Brain_Tumor-Detector', url='brain_tumor_detector',
                                         image_url='/static/images/brain_tumor_logo.png',
                                         description='Определение опухоли в мозге',
                                         pathology_id=3, target_id=2, modal_id=1)

        db.session.add(covid_detector)
        db.session.add(covid_segmentator)
        db.session.add(brain_tumor_classifier)

    db.session.commit()
    print("Тестовые данные добавлены в таблицы")

# Разрешенные типы файлов
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'dcm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        session.clear()
        form = LoginForm()
    else:
        form = LoginForm()

        if form.validate_on_submit():
            username = form.username.data
            password = form.password.data
            user = User.query.filter_by(username=username).first()
            if user == None:
                return redirect(url_for('login'))
            if password == user.password:
                with open('config/access.json') as f:
                    data = json.load(f)

                # Поиск соответствия имени пользователя в JSON
                for group_name, permissions in data.items():
                    print(group_name)
                    print(permissions)
                    if user.role == group_name:
                        print("IF")
                        session['group_name'] = group_name
                        session['username'] = username
                        print(" session['username']", session['username'])
                        user = User.query.filter_by(username=username).first()
                        session['id'] = user.id
                        print(session['id'])
                        print(session['group_name'])
                        return redirect(url_for('base'))
                else:
                    print("ELSE")
                    session['group_name'] = 'unauthorized'
                    print(session['group_name'])
                    return redirect(url_for('base'))
                # Здесь вы можете добавить логику для проверки введенных данных
                # и аутентификации пользователя
            else:
                return redirect(url_for('login'))
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/")
def base():
    return render_template("base.html")


@app.route("/covid_detector", methods=['GET', 'POST'])
def covid_detector():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'detect':
            file = request.files['file']

            if 'username' not in session:
                return redirect(url_for('login'))

            if file.filename == '':
                return render_template("covid_detector.html", error="No selected file")

            if not allowed_file(file.filename):
                return render_template("covid_detector.html", error="Not allowed type")

            if file.filename.lower().endswith('.dcm'):
                file_path = dcm_to_jpg(file)
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            try:
                model = CovidClassifier()
                model.load_state_dict(torch.load('static/covid_classifier_weights.pth'))

                start_time = datetime.now().isoformat()
                predicted_label = classify_image(file_path, model)[0]
                predicted_prob = classify_image(file_path, model)[1]

                print(predicted_label)

                image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
                image_path = os.path.join('static/images', image_filename)
                print("image_path", image_path)
                end_time = datetime.now().isoformat()

                username = session.get('username')
                user = User.query.filter_by(username=username).first()

                print("user.id", user.id)
                new_detection_log = DetectionLogs(service_id=1,
                                                  status='обработано',
                                                  name_patology=predicted_label,
                                                  percent_patology=predicted_prob,
                                                  start_time=start_time,
                                                  end_time=end_time,
                                                  user_id=user.id)

                db.session.add(new_detection_log)
                db.session.commit()

                return render_template("covid_detector.html", predicted_label=predicted_label,
                                       predicted_prob=predicted_prob,
                                       image_path=image_path,
                                       start_time=start_time, end_time=end_time)
            except RuntimeError as e:
                return render_template("covid_detector.html", error="Incorrect shape")
        elif action == 'save':
            # user = User.query.filter_by(username='username').first()
            print("session[id] ", session['id'])
            service = Service.query.filter_by(name='COVID-Classifier').first()
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            predicted_label = request.form.get('predicted_label')
            predicted_prob = request.form.get('predicted_prob')
            image_path = request.form.get('image_path')
            image_path = image_path.replace('\\', '/')
            # Создать новую запись в таблице Journal
            new_journal_entry = Journal(
                service_id=service.id,
                user_id=session['id'],
                service_result=predicted_label,
                percent_patology=predicted_prob,
                start_time=start_time,
                end_time=end_time,
                input_image_url=image_path
                # output_image_url='output_image_url_value'
            )

            # Добавить запись в сессию и сохранить в базе данных
            db.session.add(new_journal_entry)
            db.session.commit()
            return redirect(url_for('COVID_Classifier', journal_id=new_journal_entry.id))

    return render_template("covid_detector.html")


@app.route("/covid_detector/<int:journal_id>", methods=['GET', 'POST'])
def COVID_Classifier(journal_id):
    journal = Journal.query.filter_by(id=journal_id).first()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'feedback':
            print("feedback")
            return redirect(url_for('Feedback', journal_id=journal_id))
        return render_template("COVID_Classifier_journal.html", journal_id=journal_id)

    return render_template("COVID_Classifier_journal.html", journal=journal)


@app.route("/feedback", methods=['GET', 'POST'])
def Feedback():
    journal_id = request.args.get('journal_id')
    print("journal_id", journal_id)
    return render_template("feedback.html", journal_id=journal_id)


@app.route("/brain_tumor_detector", methods=['GET', 'POST'])
def brain_tumor_detector():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template("brain_tumor_detector.html", error="No file part")

        file = request.files['file']

        if file.filename == '':
            return render_template("brain_tumor_detector.html", error="No selected file")

        # if file.filename.lower().endswith('.dcm'):
        #     # Если файл DICOM, вызываем функцию для его обработки
        #     tmp_path = dcm_to_jpg(file)
        #     return render_template("covid_detector.html", image_path = tmp_path)  # Можете добавить здесь какое-то сообщение или просто вернуть шаблон

        if file and allowed_file(file.filename):
            if file.filename.lower().endswith('.dcm'):
                file_path = dcm_to_jpg(file)
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

            model = CovidClassifier()
            model.load_state_dict(torch.load('static/brain_tumor_classifier_weights.pth'))

            start_time = datetime.now().isoformat()
            predicted_label = classify_image(file_path, model)[0]
            predicted_prob = classify_image(file_path, model)[1]

            print(predicted_label)

            image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
            image_path = os.path.join('static/images', image_filename)
            end_time = datetime.now().isoformat()

            # log_detection("Обработано", end_time, 'demo_user')

            username = session.get('username')
            user = User.query.filter_by(username=username).first()

            print("user.id", user.id)
            new_detection_log = DetectionLogs(service_id=3,
                                              status='обработано',
                                              name_patology=predicted_label,
                                              percent_patology=predicted_prob,
                                              start_time=start_time,
                                              end_time=end_time,
                                              user_id=user.id)

            db.session.add(new_detection_log)
            db.session.commit()

            return render_template("brain_tumor_detector.html", predicted_label=predicted_label,
                                   predicted_prob=predicted_prob,
                                   image_path=image_path,
                                   start_time=start_time, end_time=end_time)

    return render_template("brain_tumor_detector.html")


@app.route("/covid_segmentator", methods=['GET', 'POST'])
def covid_segmentator():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template("covid_segmentator.html", error="No file part")

        file = request.files['file']

        if file.filename == '':
            return render_template("covid_segmentator.html", error="No selected file")

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

            username = session.get('username')
            user = User.query.filter_by(username=username).first()

            new_detection_log = DetectionLogs(service_id=2,
                                              status='обработано',
                                              name_patology=predicted_label,
                                              percent_patology=predicted_prob,
                                              start_time=start_time,
                                              end_time=end_time,
                                              user_id=user.id)

            db.session.add(new_detection_log)
            db.session.commit()

            return render_template("covid_segmentator.html", predicted_label=predicted_label,
                                   predicted_prob=predicted_prob,
                                   image_path=image_path,
                                   start_time=start_time, end_time=end_time)

    return render_template("covid_segmentator.html")


@app.route("/services")
def services():
    # detection_logs = DetectionLogs.query.all()
    services_list = Service.query.all()
    modals = Modal.query.all()
    targets = Target.query.all()
    pathologies = Pathology.query.all()
    return render_template("services.html", services=services_list,
                           modals=modals, targets=targets, pathologies=pathologies)


@app.route("/services/<int:service_id>", methods=["GET", "POST"])
def display_services(service_id):
    if request.method == 'POST':
        service = Service.query.get(service_id)
        return redirect(url_for(service.url))
    else:
        service = Service.query.get(service_id)
        return render_template("services_display.html", service=service)


@app.route("/logs")
def logs():
    detection_logs = DetectionLogs.query.all()

    return render_template("logs.html", detection_logs=detection_logs)


@app.route("/journal")
def journal():
    if 'username' not in session:
        return redirect(url_for('login'))

    modals = Modal.query.all()
    targets = Target.query.all()
    pathologies = Pathology.query.all()
    journal_list = Journal.query.filter_by(user_id=session['id']).all()
    return render_template("journal.html", journal_list=journal_list,
                           modals=modals, targets=targets,
                           pathologies=pathologies)


@app.route("/info")
def info():
    return render_template("info.html")


def dcm_to_jpg(path):
    ds = pydicom.dcmread(path, force=True)
    print(ds.Modality)

    # Convert DICOM to PIL Image
    if ds.Modality == "CT":
        new_image = ds.pixel_array.astype(float)
        scaled_image = (np.maximum(new_image, 0) / new_image.max()) * 255.0
        scaled_image = np.uint8(scaled_image)
        final_image = Image.fromarray(scaled_image)
        path = "static/images/test_image.png"  # TODO сделать нормальный путь для записи dicom файлов
        final_image.save(path)
        return path
    else:
        return "error modality"


if __name__ == "__main__":
    app.run(debug=True)
