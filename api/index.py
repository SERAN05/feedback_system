import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
MAIN_DIR = os.path.join(ROOT_DIR, "main")

if MAIN_DIR not in sys.path:
    sys.path.insert(0, MAIN_DIR)

from app import app
