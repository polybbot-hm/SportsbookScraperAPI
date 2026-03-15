"""Fixtures compartidos para pytest."""
import sys
from pathlib import Path

# Asegurar que app está en el path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
