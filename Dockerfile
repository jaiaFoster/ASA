FROM python:3.12.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY . /app
RUN python -m pip install --no-cache-dir .

CMD ["/bin/sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn asa.asgi:create_application --factory --host 0.0.0.0 --port \"$PORT\""]
