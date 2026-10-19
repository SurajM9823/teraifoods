FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app
COPY --chown=app:app . .
RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles
USER app
EXPOSE 8000
CMD ["python", "deploy/serve.py"]
