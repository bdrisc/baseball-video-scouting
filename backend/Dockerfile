FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY scripts/requirements.txt /tmp/scripts-requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install \
        -r /tmp/backend-requirements.txt \
        -r /tmp/scripts-requirements.txt

RUN addgroup --system app \
    && adduser --system --ingroup app app

COPY --chown=app:app backend/app ./app
COPY --chown=app:app scripts ./scripts

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
