import torch
from torchvision import transforms
from PIL import Image


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

    return predicted_label
