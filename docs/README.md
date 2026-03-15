# Documentación OpenAPI

## Archivos generados

- **openapi.json** — Especificación OpenAPI 3.0 en JSON (para Postman, Insomnia, clientes SDK).
- **openapi.yaml** — Misma especificación en YAML.

## Cómo regenerar

Desde la raíz del proyecto:

```bash
python scripts/generate_openapi.py
```

## Documentación interactiva en vivo

Con la API en marcha (`uvicorn app.main:app`):

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Schema raw:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
