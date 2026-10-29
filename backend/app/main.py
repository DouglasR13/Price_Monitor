"""
PriceRadar AI — FastAPI Entry Point.
Routes seamlessly to the Supabase PostgreSQL cloud backend.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

from app.main_supabase import app

__all__ = ["app"]
