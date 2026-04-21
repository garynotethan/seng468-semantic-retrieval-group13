FROM python:3.12-slim
WORKDIR /app
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
RUN apt-get update && apt-get install -y libpq-dev gcc
RUN pip install py-spy
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ .
COPY shared /app/shared
COPY ui /app/ui
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
