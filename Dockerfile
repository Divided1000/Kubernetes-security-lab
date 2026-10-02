FROM python:3.12-slim

WORKDIR /app

COPY app/ .

RUN apt-get update && apt-get upgrade -y

RUN pip install --upgrade pip setuptools

RUN pip install --no-cache-dir flask

EXPOSE 5000

CMD ["python", "app.py"]
