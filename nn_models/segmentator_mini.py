import torch
from torchvision import transforms
import numpy as np
from PIL import Image

def segment_and_save_image(img_path, model, output_path):
    # Предобработка изображения
    preprocess = transforms.Compose([
        transforms.ToTensor(),
        transforms.Resize((224, 224)),
        transforms.Grayscale(num_output_channels=1)
    ])

    img = Image.open(img_path)
    img_tensor = preprocess(img)

    # Нормализация
    mean = [0.5]
    std = [0.5]
    img_tensor = (img_tensor - torch.tensor(mean).view(1, 1, 1)) / torch.tensor(std).view(1, 1, 1)
    img_tensor = img_tensor.unsqueeze(0)

    # Передача изображения через модель
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    img_tensor = img_tensor.to(device)
    model = model.to(device)
    model.eval()

    with torch.no_grad():
        output = model(img_tensor)
        output = output.cpu().squeeze(0)

    # Получение сегментированной маски
    mask = output.squeeze().detach().numpy()
    mask = (mask > 0.5).astype(np.uint8)

    # Сохранение сегментированного изображения
    masked_img = Image.fromarray((mask * 255).astype(np.uint8), mode='L')
    masked_img.save(output_path)