import torch
from torchvision import transforms
from PIL import Image

# Функция для классификации изображения
def classify_image_melanoma(image_path, model, device):
    # Преобразования для изображения
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])

    # Загрузка и преобразование изображения
    image = Image.open(image_path).convert('RGB')
    image_tensor = transform(image).unsqueeze(0).to(device)

    # Переводим модель в режим оценки
    model.eval()

    # Классифицируем изображение
    with torch.no_grad():
        outputs = model(image_tensor)
        _, predicted = torch.max(outputs.data, 1)

    # Получаем название класса
    class_names = ['actinic keratosis', 'basal cell carcinoma', 'dermatofibroma', 'melanoma', 'nevus',
                   'pigmented benign keratosis', 'seborrheic keratosis', 'squamous cell carcinoma', 'vascular lesion']
    predicted_class = class_names[predicted.item()]

    return predicted_class