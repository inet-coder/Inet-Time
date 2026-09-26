FROM python:3.12-slim

WORKDIR /app

COPY apps/bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/core ./packages/core
RUN pip install --no-cache-dir -e ./packages/core

COPY apps/bot ./

CMD ["python", "main.py"]
