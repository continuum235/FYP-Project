"""ResNet50 on a small CIFAR-10 subset — real PyTorch training."""

from __future__ import annotations

import os
import threading

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
from torchvision.models import resnet50

from app.infrastructure.jobs.carbon_session import carbon_training_session

SUBSET_SIZE = 512
BATCH_SIZE = 32


def _device() -> torch.device:
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return torch.device("xpu")
    return torch.device("cpu")


def _build_loaders() -> DataLoader:
    transform = transforms.Compose(
        [
            transforms.Resize(224),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )
    train = datasets.CIFAR10(root="./data/cifar10", train=True, download=True, transform=transform)
    indices = list(range(min(SUBSET_SIZE, len(train))))
    subset = Subset(train, indices)
    return DataLoader(subset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)


def run_resnet50_cifar_job(
    *,
    cancel_event: threading.Event,
    job_id: int,
    start_epoch: int,
    total_epochs: int,
    checkpoint_path: str,
) -> dict:
    device = _device()
    model = resnet50(weights=None, num_classes=10).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    criterion = nn.CrossEntropyLoss()
    current_epoch = start_epoch
    loader = _build_loaders()

    if os.path.exists(checkpoint_path):
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        current_epoch = int(ckpt.get("epoch", start_epoch))

    paused = False
    completed = False

    with carbon_training_session(job_id, power_kw_fallback=0.15) as carbon:
        model.train()
        while current_epoch < total_epochs:
            for images, labels in loader:
                if cancel_event.is_set():
                    paused = True
                    break
                images, labels = images.to(device), labels.to(device)
                optimizer.zero_grad()
                loss = criterion(model(images), labels)
                loss.backward()
                optimizer.step()
            if paused:
                break
            current_epoch += 1

        if not paused and current_epoch >= total_epochs:
            completed = True

        os.makedirs(os.path.dirname(checkpoint_path) or ".", exist_ok=True)
        torch.save(
            {
                "epoch": current_epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
            },
            checkpoint_path,
        )

    return {
        "session_carbon_g": carbon.session_carbon_g,
        "session_energy_kwh": carbon.session_energy_kwh,
        "session_duration_hours": carbon.session_duration_hours,
        "current_epoch": current_epoch,
        "completed": completed,
        "paused": paused,
        "checkpoint_path": checkpoint_path,
    }
