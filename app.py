from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
# from flask_mail import Mail, Message
from sqlalchemy import desc, select, and_
from torch import nn
from PIL import Image, ImageDraw
import segmentation_models_pytorch as smp
from nn_models.lung_autoencoder import ConvAutoencoder
from nn_models.lung_outliers_classifier import check_lungs
from nn_models.scratch import CovidClassifier
from nn_models.classifier import classify_image, bin_classify_image
from nn_models.lung_segmentator import predict_mask, remove_small_regions
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from access import group_permission_decorator
from database import *
from forms import *
from models import *
import torchvision.models as models
import uuid
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

        pneumonia_classifier = Service(name='Pneumonia-Detector', url='pneumonia_detector',
                                       image_url='/static/images/pneumonia_logo.jpg',
                                       description='Определение пневмонии в лёгких',
                                       pathology_id=2, target_id=1, modal_id=3)

        pneumothorax_classifier = Service(name='Pneumothorax-Detector', url='pneumothorax_detector',
                                          image_url='/static/images/pneumothorax_logo.png',
                                          description='Определение пневмоторакса в лёгких',
                                          pathology_id=5, target_id=1, modal_id=3)

        melanoma_classifier = Service(name='Melanoma-Detector', url='melanoma_detector',
                                      image_url='/static/images/melanoma_logo.png',
                                      description='Определение типа меланомы на коже',
                                      pathology_id=4, target_id=5, modal_id=5)

        db.session.add(covid_detector)
        db.session.add(covid_segmentator)
        db.session.add(brain_tumor_classifier)
        db.session.add(pneumonia_classifier)
        db.session.add(pneumothorax_classifier)
        db.session.add(melanoma_classifier)

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
                ds = pydicom.dcmread(file, force=True)
                print(ds.Modality)

                # Convert DICOM to PIL Image
                if ds.Modality == "CT":
                    file_path = dcm_to_jpg(ds)
                else:
                    return render_template("covid_detector.html", error="Modality_error")
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            try:
                image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
                image_path = os.path.join('static/images', image_filename)
                print("image_path", image_path)

                image_size = (64, 64)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                lung_outliners_model = ConvAutoencoder().to(device)
                lung_outliners_model.load_state_dict(
                    torch.load('static/model_outlier_weights.pth', map_location=torch.device(device)))
                status_outliers = check_lungs(image_path, lung_outliners_model, image_size, device)
                print("status_outliers", status_outliers)
                if status_outliers == 0:
                    return render_template("covid_detector.html", error="Body_part_error")

                model = CovidClassifier()
                model.load_state_dict(torch.load('static/covid_classifier_weights.pth'))
                start_time = datetime.now().isoformat()
                predicted_label = classify_image(file_path, model)[0]
                predicted_prob = classify_image(file_path, model)[1]

                print(predicted_label)

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
                print("RuntimeError", e)
                return render_template("covid_detector.html", error="Incorrect shape")
        elif action == 'save':
            # user = User.query.filter_by(username='username').first()
            print("session[id] ", session['id'])
            service = Service.query.filter_by(url='covid_detector').first()
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
            return redirect(url_for('journal_log', journal_id=new_journal_entry.id))
    return render_template("covid_detector.html")


@app.route("/journal/<int:journal_id>", methods=['GET', 'POST'])
def journal_log(journal_id):
    journal_db = Journal.query.filter_by(id=journal_id).first()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'feedback':
            print("feedback")
            return redirect(url_for('feedback', journal_id=journal_id))
        if action == 'delete':
            db.session.delete(journal_db)
            db.session.commit()
            return redirect(url_for('journal'))
        if action == 'back':
            return redirect(url_for('journal'))
    return render_template("journal_log.html", journal=journal_db)


@app.route("/feedback", methods=['GET', 'POST'])
def feedback():
    journal_id = request.args.get('journal_id')
    journal_feedback = Journal.query.filter_by(id=journal_id).first()
    # print("journal_id", journal_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'send':
            comment = request.form.get('comment')
            is_correct = request.form.get('agree_result') == 'on'
            is_in_dataset = request.form.get('research_included') == 'on'
            print("comment", comment)
            print("is_correct", is_correct)
            print("is_in_dataset", is_in_dataset)
            # Создание нового объекта Feedback
            feedback_db = Feedback(journal_id=journal_id, comment=comment, is_correct=is_correct,
                                   is_in_dataset=is_in_dataset)
            # Добавление объекта в базу данных
            db.session.add(feedback_db)
            db.session.commit()
            return redirect(url_for('journal'))
        if action == 'back':
            return redirect(url_for('journal'))
    return render_template("feedback.html", journal=journal_feedback)


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
        action = request.form.get('action')
        if action == 'detect':
            file = request.files['file']

            if 'username' not in session:
                return redirect(url_for('login'))

            if file.filename == '':
                return render_template("covid_segmentator.html", error="No selected file")

            if not allowed_file(file.filename):
                return render_template("covid_segmentator.html", error="Not allowed type")

            if file.filename.lower().endswith('.dcm'):
                ds = pydicom.dcmread(file, force=True)
                print(ds.Modality)

                # Convert DICOM to PIL Image
                if ds.Modality == "CT":
                    file_path = dcm_to_jpg(ds)
                else:
                    return render_template("covid_segmentator.html", error="Modality_error")
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            try:
                image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
                image_path = os.path.join('static/images', image_filename)
                print("image_path", image_path)

                image_size = (64, 64)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                lung_outliners_model = ConvAutoencoder().to(device)
                lung_outliners_model.load_state_dict(
                    torch.load('static/model_outlier_weights.pth', map_location=torch.device(device)))
                status_outliers = check_lungs(image_path, lung_outliners_model, image_size, device)
                print("status_outliers", status_outliers)
                if status_outliers == 0:
                    return render_template("covid_segmentator.html", error="Body_part_error")

                image_size = (256, 256)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

                lung_model = smp.Unet(
                    encoder_name="resnet34",
                    encoder_weights="imagenet",
                    in_channels=1,
                    classes=1,
                )

                infection_model = smp.Unet(
                    encoder_name='timm-resnest101e',
                    encoder_weights='imagenet',
                    in_channels=1,
                    classes=1
                )

                lung_model.to(device)
                infection_model.to(device)

                lung_model.load_state_dict(
                    torch.load('static/segmentation_model_lung_weights.pth', map_location=device))
                infection_model.load_state_dict(
                    torch.load('static/segmentation_model_infection_weights.pth', map_location=device))

                start_time = datetime.now().isoformat()

                predicted_lung_mask = predict_mask(image_path, lung_model, image_size, device)
                predicted_infection_mask = predict_mask(image_path, infection_model, image_size, device)

                predicted_lung_mask = remove_small_regions(predicted_lung_mask)
                predicted_infection_mask = np.where(predicted_lung_mask == 1, predicted_infection_mask, 0)

                num_lung_pixels = np.sum(predicted_lung_mask)
                num_infection_pixels = np.sum(predicted_infection_mask)

                if num_lung_pixels > 0:
                    lung_infection_percentage = (num_infection_pixels / num_lung_pixels) * 100
                else:
                    lung_infection_percentage = 0

                name_patology = 'COVID' if lung_infection_percentage > 1 else 'Normal'

                image = Image.open(image_path).convert('RGBA')
                image = image.resize((256, 256))

                predicted_lung_mask = Image.fromarray(np.uint8(predicted_lung_mask * 255), mode='L')
                predicted_infection_mask = Image.fromarray(np.uint8(predicted_infection_mask * 255), mode='L')

                # Создание полупрозрачных масок
                lung_alpha = predicted_lung_mask.point(lambda p: p * 0.3)
                infection_alpha = predicted_infection_mask.point(lambda p: p * 0.3)

                lung_overlay = Image.new('RGBA', image.size, (0, 128, 0, 32))  # Зеленый цвет
                lung_overlay.putalpha(lung_alpha)

                infection_overlay = Image.new('RGBA', image.size, (128, 0, 0, 32))  # Красный цвет
                infection_overlay.putalpha(infection_alpha)

                # Наложение масок на изображение
                image = Image.alpha_composite(image, lung_overlay)
                image = Image.alpha_composite(image, infection_overlay)

                uid = str(uuid.uuid4()) + "segmentation.png"
                output_path = os.path.join("static/images", f'{uid}.png')

                image.save(output_path)

                end_time = datetime.now().isoformat()

                username = session.get('username')
                user = User.query.filter_by(username=username).first()

                print("user.id", user.id)
                new_detection_log = DetectionLogs(service_id=1,
                                                  status='обработано',
                                                  name_patology=name_patology,
                                                  percent_patology=f"{lung_infection_percentage:.2f}",
                                                  start_time=start_time,
                                                  end_time=end_time,
                                                  user_id=user.id)

                db.session.add(new_detection_log)
                db.session.commit()

                return render_template("covid_segmentator.html", predicted_label=name_patology,
                                       predicted_prob=f"{lung_infection_percentage:.2f}",
                                       image_path=output_path, input_path=image_path,
                                       start_time=start_time, end_time=end_time)
            except RuntimeError as e:
                print("RuntimeError", e)
                return render_template("covid_segmentator.html", error="Incorrect shape")
        elif action == 'save':
            # user = User.query.filter_by(username='username').first()
            print("session[id] ", session['id'])
            service = Service.query.filter_by(url='covid_segmentator').first()
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            predicted_label = request.form.get('predicted_label')
            predicted_prob = request.form.get('predicted_prob')
            image_path = request.form.get('image_path')
            input_path = request.form.get('input_path')

            image_path = image_path.replace('\\', '/')
            input_path = input_path.replace('\\', '/')

            # Создать новую запись в таблице Journal
            new_journal_entry = Journal(
                service_id=service.id,
                user_id=session['id'],
                service_result=predicted_label,
                percent_patology=predicted_prob,
                start_time=start_time,
                end_time=end_time,
                input_image_url=input_path,
                output_image_url=image_path
            )

            # Добавить запись в сессию и сохранить в базе данных
            db.session.add(new_journal_entry)
            db.session.commit()
            return redirect(url_for('journal_log', journal_id=new_journal_entry.id))
    return render_template("covid_segmentator.html")


@app.route("/pneumonia_detector", methods=['GET', 'POST'])
def pneumonia_detector():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'detect':
            file = request.files['file']

            if 'username' not in session:
                return redirect(url_for('login'))

            if file.filename == '':
                return render_template("pneumonia_detector.html", error="No selected file")

            if not allowed_file(file.filename):
                return render_template("pneumonia_detector.html", error="Not allowed type")

            if file.filename.lower().endswith('.dcm'):
                ds = pydicom.dcmread(file, force=True)
                print(ds.Modality)

                # Convert DICOM to PIL Image
                if ds.Modality == "CT":
                    file_path = dcm_to_jpg(ds)
                else:
                    return render_template("pneumonia_detector.html", error="Modality_error")
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            try:
                image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
                image_path = os.path.join('static/images', image_filename)
                print("image_path", image_path)

                image_size = (64, 64)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                lung_outliners_model = ConvAutoencoder().to(device)
                lung_outliners_model.load_state_dict(
                    torch.load('static/model_outlier_weights.pth', map_location=torch.device(device)))
                status_outliers = check_lungs(image_path, lung_outliners_model, image_size, device)
                print("status_outliers", status_outliers)
                if status_outliers == 0:
                    return render_template("pneumonia_detector.html", error="Body_part_error")

                class_labels_pneumonia = ['Pneumonia', 'Normal']
                resnet_model = models.resnet18(weights='DEFAULT')
                num_ftrs = resnet_model.fc.in_features
                resnet_model.fc = nn.Linear(num_ftrs, 2)  # Заменяем на выход из 2 классов (ваш случай)
                resnet_weights = "static/pneumonia_classifier_resnet_weights.pth"
                resnet_model.load_state_dict(torch.load(resnet_weights, map_location=torch.device(device)))

                # model = CovidClassifier()
                # model.load_state_dict(torch.load('static/covid_classifier_weights.pth'))
                #

                start_time = datetime.now().isoformat()
                predicted_label = bin_classify_image(file_path, resnet_model, class_labels_pneumonia)[0]
                predicted_prob = bin_classify_image(file_path, resnet_model, class_labels_pneumonia)[1]

                print(predicted_label)

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

                return render_template("pneumonia_detector.html", predicted_label=predicted_label,
                                       predicted_prob=predicted_prob,
                                       image_path=image_path,
                                       start_time=start_time, end_time=end_time)
            except RuntimeError as e:
                print("RuntimeError", e)
                return render_template("pneumonia_detector.html", error="Incorrect shape")
        elif action == 'save':
            # user = User.query.filter_by(username='username').first()
            print("session[id] ", session['id'])
            service = Service.query.filter_by(url='pneumonia_detector').first()
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
            return redirect(url_for('journal_log', journal_id=new_journal_entry.id))
    return render_template("pneumonia_detector.html")


@app.route("/pneumothorax_detector", methods=['GET', 'POST'])
def pneumothorax_detector():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'detect':
            file = request.files['file']

            if 'username' not in session:
                return redirect(url_for('login'))

            if file.filename == '':
                return render_template("pneumothorax_detector.html", error="No selected file")

            if not allowed_file(file.filename):
                return render_template("pneumothorax_detector.html", error="Not allowed type")

            if file.filename.lower().endswith('.dcm'):
                ds = pydicom.dcmread(file, force=True)
                print(ds.Modality)

                # Convert DICOM to PIL Image
                if ds.Modality == "CT":
                    file_path = dcm_to_jpg(ds)
                else:
                    return render_template("pneumothorax_detector.html", error="Modality_error")
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            try:
                image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
                image_path = os.path.join('static/images', image_filename)
                print("image_path", image_path)

                image_size = (64, 64)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                lung_outliners_model = ConvAutoencoder().to(device)
                lung_outliners_model.load_state_dict(
                    torch.load('static/model_outlier_weights.pth', map_location=torch.device(device)))
                status_outliers = check_lungs(image_path, lung_outliners_model, image_size, device)
                print("status_outliers", status_outliers)
                if status_outliers == 0:
                    return render_template("pneumothorax_detector.html", error="Body_part_error")

                class_labels_pneumothorax = ['Pneumothorax', 'Normal']
                resnet_model = models.resnet18(weights='DEFAULT')
                num_ftrs = resnet_model.fc.in_features
                resnet_model.fc = nn.Linear(num_ftrs, 2)  # Заменяем на выход из 2 классов (ваш случай)
                resnet_weights = "static/pneumothorax_classifier_resnet_weights.pth"
                resnet_model.load_state_dict(torch.load(resnet_weights, map_location=torch.device(device)))

                start_time = datetime.now().isoformat()
                predicted_label = bin_classify_image(file_path, resnet_model, class_labels_pneumothorax)[0]
                predicted_prob = bin_classify_image(file_path, resnet_model, class_labels_pneumothorax)[1]

                print(predicted_label)

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

                return render_template("pneumothorax_detector.html", predicted_label=predicted_label,
                                       predicted_prob=predicted_prob,
                                       image_path=image_path,
                                       start_time=start_time, end_time=end_time)
            except RuntimeError as e:
                print("RuntimeError", e)
                return render_template("pneumothorax_detector.html", error="Incorrect shape")
        elif action == 'save':
            # user = User.query.filter_by(username='username').first()
            print("session[id] ", session['id'])
            service = Service.query.filter_by(url='pneumothorax_detector').first()
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
            return redirect(url_for('journal_log', journal_id=new_journal_entry.id))
    return render_template("pneumothorax_detector.html")


@app.route("/melanoma_detector", methods=['GET', 'POST'])
def melanoma_detector():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'detect':
            file = request.files['file']

            if 'username' not in session:
                return redirect(url_for('login'))

            if file.filename == '':
                return render_template("melanoma_detector.html", error="No selected file")

            if not allowed_file(file.filename):
                return render_template("melanoma_detector.html", error="Not allowed type")

            if file.filename.lower().endswith('.dcm'):
                ds = pydicom.dcmread(file, force=True)
                print(ds.Modality)

                # Convert DICOM to PIL Image
                if ds.Modality == "CT":
                    file_path = dcm_to_jpg(ds)
                else:
                    return render_template("melanoma_detector.html", error="Modality_error")
            else:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            try:
                image_filename = os.path.basename(file_path)  # Получаем имя файла из полного пути
                image_path = os.path.join('static/images', image_filename)
                print("image_path", image_path)

                image_size = (64, 64)
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                lung_outliners_model = ConvAutoencoder().to(device)
                lung_outliners_model.load_state_dict(
                    torch.load('static/model_outlier_weights.pth', map_location=torch.device(device)))
                status_outliers = check_lungs(image_path, lung_outliners_model, image_size, device)
                print("status_outliers", status_outliers)
                if status_outliers == 0:
                    return render_template("melanoma_detector.html", error="Body_part_error")

                model = CovidClassifier()
                model.load_state_dict(torch.load('static/covid_classifier_weights.pth'))
                start_time = datetime.now().isoformat()
                predicted_label = classify_image(file_path, model)[0]
                predicted_prob = classify_image(file_path, model)[1]

                print(predicted_label)

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

                return render_template("melanoma_detector.html", predicted_label=predicted_label,
                                       predicted_prob=predicted_prob,
                                       image_path=image_path,
                                       start_time=start_time, end_time=end_time)
            except RuntimeError as e:
                print("RuntimeError", e)
                return render_template("melanoma_detector.html", error="Incorrect shape")
        elif action == 'save':
            # user = User.query.filter_by(username='username').first()
            print("session[id] ", session['id'])
            service = Service.query.filter_by(url='melanoma_detector').first()
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
            return redirect(url_for('journal_log', journal_id=new_journal_entry.id))
    return render_template("melanoma_detector.html")


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
        if 'username' not in session:
            return redirect(url_for('login'))
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
    # journal_list = Journal.query.filter_by(user_id=session['id']).all()
    journal_list = Journal.query.filter_by(user_id=session['id']).order_by(desc(Journal.end_time)).all()
    return render_template("journal.html", journal_list=journal_list,
                           modals=modals, targets=targets,
                           pathologies=pathologies)


@app.route("/info")
def info():
    return render_template("info.html")


@app.route('/dicom_analysis', methods=['GET', 'POST'])
def dicom_analysis():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'detect':
            file = request.files['file']

            if file.filename == '':
                return render_template("dicom_analysis.html", error="No selected file")

            if file.filename.lower().endswith('.dcm'):
                ds = pydicom.dcmread(file, force=True)
                # print(ds)

                body_part = ds.get((0x0018, 0x0015))
                body_part = str(body_part.value).strip()

                patient_identity_removed = ds.get((0x0012, 0x0062))
                patient_identity_removed = str(patient_identity_removed.value).strip()

                new_image = ds.pixel_array.astype(float)
                scaled_image = (np.maximum(new_image, 0) / new_image.max()) * 255.0
                scaled_image = np.uint8(scaled_image)
                final_image = Image.fromarray(scaled_image)
                unique_filename = str(uuid.uuid4()) + ".png"
                path = "static/images/" + unique_filename
                final_image.save(path)
                return render_template("dicom_analysis.html", modality=ds.Modality, body_part=body_part,
                                       patient_identity_removed=patient_identity_removed, path=path)
            else:
                return render_template("dicom_analysis.html", error="Not allowed type")

    return render_template('dicom_analysis.html')


def dcm_to_jpg(ds):
    # Convert DICOM to PIL Image
    new_image = ds.pixel_array.astype(float)
    scaled_image = (np.maximum(new_image, 0) / new_image.max()) * 255.0
    scaled_image = np.uint8(scaled_image)
    final_image = Image.fromarray(scaled_image)
    unique_filename = str(uuid.uuid4()) + ".png"
    path = "static/images/" + unique_filename
    final_image.save(path)
    return path


if __name__ == "__main__":
    app.run(debug=True)
