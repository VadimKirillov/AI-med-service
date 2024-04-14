import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from torchvision.transforms import transforms

transform = transforms.Compose([
    transforms.Resize((224, 224)),  # Изменяем размер всех изображений до 224x224
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


batch_size = 32


# Определяем модель
class BrainTumorClassifier(nn.Module):
    def __init__(self):  # Исправлено с "def init(self):"
        super(BrainTumorClassifier, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, 3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        # В вашем коде возможна ошибка в размере входа в fc1, нужно проверить размер после сверток и пулинга
        self.fc1 = nn.Linear(64 * 28 * 28, 128)  # Этот размер может быть неверным в зависимости от размеров изображения после сверточных и пулинг слоев
        self.fc2 = nn.Linear(128, 2)
        self.dropout = nn.Dropout(0.25)

    def forward(self, x):
        x = self.pool(torch.relu(self.conv1(x)))
        x = self.pool(torch.relu(self.conv2(x)))
        x = self.pool(torch.relu(self.conv3(x)))
        # Важно исправить размер входа в первый полносвязный слой после определения фактического размера тензора
        x = x.view(-1, 64 * 28 * 28)  # Этот размер потребуется пересчитать
        x = self.dropout(torch.relu(self.fc1(x)))
        x = self.fc2(x)
        return x