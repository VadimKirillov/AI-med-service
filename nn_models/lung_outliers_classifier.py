import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from PIL import Image
from torchvision.transforms import Compose, Resize, ToTensor

image_size = (64, 64)

# Создание новой модели и загрузка весов
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
new_model = ConvAutoencoder().to(device)
new_model.load_state_dict(torch.load('C:/Users/79629/Desktop/2сем_мага/ИИ-сервис в медицине/model_outlier_weights.pth'))

# Функция для расчета MSE между выходом модели и входными данными
def calculate_mse(inputs, outputs):
    criterion = nn.MSELoss()
    mse = criterion(outputs, inputs)
    return mse.item()

# Функция для предобработки изображения
def preprocess_image(image_path):
    # Определение преобразований для данных
    transforms = Compose([
    Resize(image_size),
    ToTensor()
    ])
    image = Image.open(image_path).convert('RGB')
    image_tensor = transforms(image).unsqueeze(0)
    return image_tensor.to(device)

# Функция для расчета MSE для отдельного изображения
def calculate_mse_for_image(image_path):
    new_model.eval()
    with torch.no_grad():
        image_tensor = preprocess_image(image_path)
        output = new_model(image_tensor)
        mse = calculate_mse(image_tensor, output)
    return mse

# Функция для расчета MSE для отдельного изображения
def check_lungs(image_path):
    mse = calculate_mse_for_image(image_path)
    if mse > 0.003:
        return 0
    else:
        return 1