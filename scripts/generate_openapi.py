"""
Genera la especificación OpenAPI (openapi.json y openapi.yaml) desde la app FastAPI.
Ejecutar desde la raíz del proyecto: python scripts/generate_openapi.py
"""
import json
import sys
from pathlib import Path

# Raíz del proyecto
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.main import app

out_dir = root / "docs"
out_dir.mkdir(exist_ok=True)

# OpenAPI 3.0 schema generado por FastAPI
openapi = app.openapi()

# JSON
json_path = out_dir / "openapi.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(openapi, f, ensure_ascii=False, indent=2)
print(f"Generado: {json_path}")

# YAML (opcional, requiere PyYAML)
try:
    import yaml
    yaml_path = out_dir / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(openapi, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"Generado: {yaml_path}")
except ImportError:
    print("Para generar openapi.yaml instala: pip install pyyaml")
