FROM python:3.12-slim
ARG VERSION=dev
ENV VERSION=${VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml .
COPY simulator ./simulator
COPY scenarios ./scenarios
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["uvicorn", "simulator.app:app", "--host", "0.0.0.0", "--port", "8080"]
