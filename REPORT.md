# 🚀 FastAPI Observability Stack - PR Debugging Report

Este proyecto ha sido optimizado y depurado para garantizar la estabilidad en entornos de producción y CI/CD utilizando **Python 3.13.12**.

## 🛠️ Bugs Depurados y Mejoras (Niveles 1-3)

### 1. Robustez del Tráfico (Locust)
- **Bug:** Se detectó un *Function Shadowing* en `locustfile.py` donde dos tareas compartían el mismo nombre (`random_sleep`), causando que una sobreescribiera a la otra.
- **Solución:** Refactorización de nombres de tareas para garantizar la cobertura total de los endpoints de prueba, incluyendo el monitoreo de errores inducidos.

### 2. Estabilidad de Dependencias
- **Mejora:** Ajuste de versiones en `pyproject.toml` para **OpenTelemetry** (v1.30.0 / v0.51b0). Esto soluciona problemas de compatibilidad con los hooks de importación de Python 3.13, evitando fugas de memoria en el colector.

### 3. Infraestructura y Seguridad
- **Docker Compose V2:** Migración de sintaxis de `docker-compose` a `docker compose` para compatibilidad con runners modernos de GitHub Actions.
- **Seguridad de Red:** Se restringió el acceso a Prometheus, Tempo y Loki a `127.0.0.1` en el mapeo de puertos, protegiendo el stack de accesos externos no autorizados.

### 4. Correlación de Observabilidad (Nivel 3)
- **Exemplars en Prometheus:** Configuración de `enable_protobuf_negotiation: true` para permitir el salto directo de métricas a trazas.
- **Loki Logging Plugin:** Integración del driver de logs de Grafana en el flujo de CI, permitiendo la persistencia y centralización de logs incluso en entornos efímeros.

### 5. CI/CD Pipeline
- **Workflow Resilience:** Implementación de `workflow_dispatch` para pruebas manuales y configuración de Locust con `--exit-code-on-error 0` para validar la captura de errores 4xx/5xx sin romper el pipeline de integración.

