FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1 STOCK_DATA_DIR=/data
EXPOSE 8080
CMD ["python", "worker.py"]
