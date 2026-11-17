FROM python:3.12-slim
ARG VERSION=dev
ENV VERSION=${VERSION}
WORKDIR /app
COPY app.py .
EXPOSE 8080
CMD ["python", "app.py"]