import asyncio  # FIX: Necesario para no bloquear el event loop
import logging
import os
import random
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, Response
from opentelemetry.propagate import inject
from utils import PrometheusMiddleware, metrics, setting_otlp

APP_NAME = os.environ.get("APP_NAME", "app")
EXPOSE_PORT = int(os.environ.get("EXPOSE_PORT", 8000))
OTLP_GRPC_ENDPOINT = os.environ.get("OTLP_GRPC_ENDPOINT", "tempo:4317")
TARGET_ONE_HOST = os.environ.get("TARGET_ONE_HOST", "app-b")
TARGET_TWO_HOST = os.environ.get("TARGET_TWO_HOST", "app-c")

app = FastAPI()

# Setting metrics middleware
app.add_middleware(PrometheusMiddleware, app_name=APP_NAME)
app.add_route("/metrics", metrics)

# Setting OpenTelemetry exporter
setting_otlp(app, APP_NAME, OTLP_GRPC_ENDPOINT)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

@app.get("/")
async def read_root():
    logging.error("Hello World")
    return {"Hello": "World"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Optional[str] = None):
    logging.error("items")
    return {"item_id": item_id, "q": q}

@app.get("/io_task")
async def io_task():
    # FIX: await asyncio.sleep permite que el loop atienda otras peticiones
    await asyncio.sleep(1) 
    logging.error("io task")
    return "IO bound task finish!"

@app.get("/cpu_task")
async def cpu_task():
    for i in range(1000):
        _ = i * i * i
        # Tip: En tareas CPU intensivas reales, se usaría un executor, 
        # pero para mantener la lógica del autor sin bloquear, esto ayuda:
        if i % 100 == 0:
            await asyncio.sleep(0) 
    logging.error("cpu task")
    return "CPU bound task finish!"

@app.get("/random_status")
async def random_status(response: Response):
    response.status_code = random.choice([200, 200, 300, 400, 500])
    logging.error("random status")
    return {"path": "/random_status"}

@app.get("/random_sleep")
async def random_sleep(response: Response):
    # FIX: Cambiado a asíncrono. Ahora Siege no colapsará la app.
    await asyncio.sleep(random.randint(0, 5))
    logging.error("random sleep")
    return {"path": "/random_sleep"}

@app.get("/error_test")
async def error_test(response: Response):
    logging.error("got error!!!!")
    raise ValueError("value error")

@app.get("/chain")
async def chain(response: Response):
    headers = {}
    inject(headers)
    logging.critical(headers)

    async with httpx.AsyncClient() as client:
        # Nota: Se usa localhost:EXPOSE_PORT para ser dinámicos
        await client.get(f"http://localhost:{EXPOSE_PORT}/", headers=headers)
        await client.get(f"http://{TARGET_ONE_HOST}:8000/io_task", headers=headers)
        await client.get(f"http://{TARGET_TWO_HOST}:8000/cpu_task", headers=headers)
    
    logging.info("Chain Finished")
    return {"path": "/chain"}

if __name__ == "__main__":
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = (
        "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] "
        "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] - %(message)s"
    )
    uvicorn.run(app, host="0.0.0.0", port=EXPOSE_PORT, log_config=log_config)

