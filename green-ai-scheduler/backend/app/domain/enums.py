from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    MANUALLY_PAUSED = "MANUALLY_PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobType(str, Enum):
    RESNET50_CIFAR = "resnet50_cifar"
    BERT_IMDB = "bert_imdb"
    SIMULATED = "simulated"


class Action(str, Enum):
    RUN = "RUN"
    WAIT = "WAIT"
    PAUSE = "PAUSE"
