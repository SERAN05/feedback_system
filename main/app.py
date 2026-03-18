import importlib
import sys

admin_src = importlib.import_module("admin.src")
sys.modules.setdefault("src", admin_src)
admin_summarizer = importlib.import_module("admin.summarizer")
sys.modules.setdefault("summarizer", admin_summarizer)

from src.main import create_app

app = create_app()

__all__ = ["app", "create_app"]
