FROM python:3.11-slim

WORKDIR /app

COPY docker/requirements.standalone.txt ./requirements.standalone.txt
RUN pip install --no-cache-dir \
	--retries 20 \
	--timeout 120 \
	--trusted-host pypi.org \
	--trusted-host files.pythonhosted.org \
	-r requirements.standalone.txt

COPY . .

RUN mkdir -p models/weights datasets logs

EXPOSE 8001

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8001"]
