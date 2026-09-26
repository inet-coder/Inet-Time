FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY apps/scheduler/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/core ./packages/core
RUN pip install --no-cache-dir -e ./packages/core

COPY apps/scheduler ./

CMD ["python", "main.py"]
