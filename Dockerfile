FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.110" "uvicorn[standard]>=0.29" "pydantic>=2" "pydantic-settings>=2" \
    "SQLAlchemy>=2" "scikit-learn>=1.3" "numpy>=1.26" "prometheus-client>=0.20"

COPY aegis ./aegis
COPY static ./static

# Non-root
RUN useradd -m app && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"
CMD ["uvicorn", "aegis.main:app", "--host", "0.0.0.0", "--port", "8000"]
