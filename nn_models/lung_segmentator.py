import torch
from PIL import Image
from torchvision.transforms import Compose, Resize, ToTensor
import cv2
import numpy as np

def predict_mask(image_path, model, image_size, device):
    transforms = Compose([
        Resize(image_size),
        ToTensor()
    ])
    # Загружаем изображение и преобразуем его в тензор
    image = Image.open(image_path).convert("L")
    image_tensor = transforms(image).unsqueeze(0).to(device)  # Добавляем размерность батча и перемещаем на устройство

    # Предсказание моделью
    model.eval()
    with torch.no_grad():
        pred_mask = model(image_tensor)
        pred_mask = torch.sigmoid(pred_mask)
        pred_mask = (pred_mask > 0.5).float()  # Бинаризация предсказания

    return pred_mask.squeeze().cpu().numpy()  # Возвращаем маску как numpy массив


def remove_small_regions(binary_mask):
    # Находим контуры на бинарной маске
    contours, _ = cv2.findContours(binary_mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # Вычисляем площади контуров
    areas = [cv2.contourArea(c) for c in contours]

    # Сортируем контуры по убыванию площади
    sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)

    # Создаем новую маску, содержащую только две самые крупные области
    mask = np.zeros_like(binary_mask)
    cv2.drawContours(mask, sorted_contours[:2], -1, 1, -1)

    return mask
