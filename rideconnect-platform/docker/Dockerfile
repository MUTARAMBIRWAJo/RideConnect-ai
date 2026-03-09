FROM python:3.11-slim

WORKDIR /app

COPY rideconnect-platform/docker/requirements.enterprise.txt /app/requirements.enterprise.txt
RUN pip install --no-cache-dir -r /app/requirements.enterprise.txt

COPY rideconnect-platform /app/rideconnect-platform
WORKDIR /app/rideconnect-platform

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/rideconnect-platform
