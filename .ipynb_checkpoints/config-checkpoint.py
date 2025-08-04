"""Конфигурация приложения"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    # Elasticsearch
    ES_HOST: str = os.getenv("ES_HOST", "http://vps-ml01.ois.ru:9200")
    ES_INDEX: str = os.getenv("ES_INDEX", "oil-well-reports")
    DOC_INDEX: str = os.getenv("DOC_INDEX", "belaruss-guide-index")

    # AI Model
    MODEL_PATH: str = os.getenv("MODEL_PATH", "unsloth/phi-4-unsloth-bnb-4bit")
    MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", "/home/ois.ru/mvprokhorova/models")

    # App Settings
    MAX_PLOT_FILES: int = int(os.getenv("MAX_PLOT_FILES", "20"))
    MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "10000"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))

    # Debug
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Page Config
    PAGE_TITLE: str = "OIS-GPT"
    PAGE_ICON: str = "🤖"
    LAYOUT: str = "wide"


config = Config()