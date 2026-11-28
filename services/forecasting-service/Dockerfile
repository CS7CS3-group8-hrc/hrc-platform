FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py metrics.py ./
EXPOSE 8080 9100
CMD ["python", "app.py"]
