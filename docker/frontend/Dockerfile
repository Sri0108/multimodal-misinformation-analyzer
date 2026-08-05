# ---------- Build Stage ----------
FROM node:20-bookworm-slim AS builder

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci

COPY frontend/ .

RUN npm run build

# ---------- Runtime Stage ----------
FROM nginx:alpine

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx","-g","daemon off;"]