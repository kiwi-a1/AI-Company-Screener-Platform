"""Launch the app with SYNTHETIC Yahoo data (tests/fake_yahoo.py) for offline UI checks.

    python -m tests.run_offline        # then open http://localhost:8501
"""
import sys
from pathlib import Path

from streamlit.web import bootstrap

from tests import fake_yahoo

if __name__ == "__main__":
    fake_yahoo.install()
    app = str(Path(__file__).resolve().parent.parent / "app.py")
    bootstrap.run(app, False, sys.argv[1:], {"server.port": 8501, "server.headless": True})
