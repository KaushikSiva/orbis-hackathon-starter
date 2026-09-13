FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SHOWROOM_DATA_DIR=/var/data/showroom
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /build/frontend/dist /app/frontend/dist
COPY scripts/start-production.sh /app/scripts/start-production.sh
RUN mkdir -p /var/data/showroom
EXPOSE 10000
CMD ["sh", "/app/scripts/start-production.sh"]
