import torch
from torchvision import transforms
from PIL import Image
import torch.nn.functional as F

# Преобразования для нового изображения
transform = transforms.Compose([
    transforms.Resize(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


# Функция для классификации нового изображения
def classify_image(image_path, model):
    # Загружаем и преобразуем изображение
    image = Image.open(image_path).convert('RGB')
    image_tensor = transform(image).unsqueeze(0)

    # Переводим модель в режим оценки
    model.eval()

    # Классифицируем изображение
    with torch.no_grad():
        output = model(image_tensor)
        _, predicted = torch.max(output.data, 1)

    # Получаем метку класса
    class_labels = ['COVID', 'Normal']
    predicted_label = class_labels[predicted.item()]
    probabilities = F.softmax(output, dim=1)
    first_class_probability = round(probabilities[0][0].item() * 100, 3)

    return predicted_label, first_class_probability


def bin_classify_image(image_path, model, class_labels):
    # Загружаем и преобразуем изображение
    image = Image.open(image_path).convert('RGB')
    image_tensor = transform(image).unsqueeze(0)

    # Переводим модель в режим оценки
    model.eval()

    # Классифицируем изображение
    with torch.no_grad():
        output = model(image_tensor)
        _, predicted = torch.max(output.data, 1)

    # Получаем метку класса

    predicted_label = class_labels[predicted.item()]
    probabilities = F.softmax(output, dim=1)
    first_class_probability = round(probabilities[0][0].item() * 100, 3)

    return predicted_label, first_class_probability
