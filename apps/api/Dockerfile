FROM python:3.12-slim

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/core ./packages/core
RUN pip install --no-cache-dir -e ./packages/core

COPY apps/api ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
