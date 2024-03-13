from flask import Flask, render_template, request
from models.scratch import CovidClassifier
from models.classifier import classify_image
from werkzeug.utils import secure_filename
from datetime import datetime
import torch
import os

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'static/images'
# Разрешенные типы файлов
ALLOWED_EXTENSIONS = {'png', 'jpg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template("index.html", error="No file part")

        file = request.files['file']

        if file.filename == '':
            return render_template("index.html", error="No selected file")

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

            return render_template("index.html", predicted_label=predicted_label, predicted_prob=predicted_prob,
                                   image_path=image_path,
                                   start_time=start_time, end_time=end_time)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)