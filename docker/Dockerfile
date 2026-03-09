FROM python:3.11-slim

WORKDIR /app

COPY docker/requirements.standalone.txt ./requirements.standalone.txt
RUN pip install --no-cache-dir -r requirements.standalone.txt

COPY . .

RUN mkdir -p models/weights datasets logs

EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
