"""DistilBERT fine-tune on a small IMDB subset — real Hugging Face training."""

from __future__ import annotations

import os
import threading

# Avoid HF tokenizers forking warnings / stray subprocess issues during DataLoader map
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch
from datasets import load_dataset
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.infrastructure.jobs.carbon_session import carbon_training_session

SUBSET_SIZE = 200
BATCH_SIZE = 8
MODEL_NAME = "distilbert-base-uncased"
IMDB_DATASET = "stanfordnlp/imdb"  # "imdb" alone breaks on newer `datasets` (HfUriError)


def _device() -> torch.device:
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return torch.device("xpu")
    return torch.device("cpu")


def _build_loaders(tokenizer):
    ds = load_dataset(IMDB_DATASET, split=f"train[:{SUBSET_SIZE}]")

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)

    ds = ds.map(tokenize, batched=True, num_proc=None)
    ds.set_format(type="torch", columns=["input_ids", "attention_mask", "label"])
    return DataLoader(ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)


def run_bert_imdb_job(
    *,
    cancel_event: threading.Event,
    job_id: int,
    start_epoch: int,
    total_epochs: int,
    checkpoint_path: str,
) -> dict:
    device = _device()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)
    loader = _build_loaders(tokenizer)
    current_epoch = start_epoch

    if os.path.exists(checkpoint_path):
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        current_epoch = int(ckpt.get("epoch", start_epoch))

    paused = False
    completed = False

    with carbon_training_session(job_id, power_kw_fallback=0.12) as carbon:
        model.train()
        while current_epoch < total_epochs:
            for batch in loader:
                if cancel_event.is_set():
                    paused = True
                    break
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["label"].to(device)
                optimizer.zero_grad()
                outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                outputs.loss.backward()
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
