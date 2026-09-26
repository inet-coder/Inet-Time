FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY apps/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/core ./packages/core
RUN pip install --no-cache-dir -e ./packages/core

COPY apps/worker ./

CMD ["arq", "worker.WorkerSettings"]
