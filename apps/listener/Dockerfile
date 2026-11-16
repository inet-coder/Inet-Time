FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY apps/listener/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Core kutubxonalari (telethon, openai, sqlalchemy...) alohida qatlamda: faqat pyproject.toml o'zgarsa qayta
# o'rnatiladi. Kod o'zgarganda deploy tez va kam xotira bilan o'tadi.
COPY packages/core/pyproject.toml ./packages/core/pyproject.toml
RUN mkdir -p packages/core/core && touch packages/core/core/__init__.py \
    && pip install --no-cache-dir -e ./packages/core
COPY packages/core ./packages/core

COPY apps/listener ./

CMD ["python", "main.py"]
