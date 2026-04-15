import os
import sys

# Add the project's `api/` folder to sys.path so tests can `import sync_payments`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)
