# Etapa 1 - instalarea dependentelor intr-un mediu virtual separat.
# Uneltele de compilare a pachetelor raman in aceasta etapa.
FROM python:3.13-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Etapa 2 - executie. Primeste doar mediul virtual si codul sursa.
FROM python:3.13-slim
LABEL org.opencontainers.image.title="MAP proiect" \
      org.opencontainers.image.authors="Nume Prenume <email@student.upt.ro>" \
      org.opencontainers.image.source="https://github.com/utilizator/repo"

ARG COMMIT=dev
ARG BUILT_AT=unknown
ENV APP_COMMIT=$COMMIT \
    APP_BUILT_AT=$BUILT_AT \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY src/ ./src/
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "src.app:app"]
