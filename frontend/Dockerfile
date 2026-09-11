# Stage 1: Build the production static React/Vite assets
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests
COPY package*.json ./

# Install npm dependencies
RUN npm ci

# Copy frontend source
COPY . .

# Build production bundle with default API base URL configured for relative /api routing
ENV VITE_API_BASE_URL=""
RUN npm run build

# Stage 2: Production Nginx Server
FROM nginx:1.27-alpine

# Remove default nginx website configuration
RUN rm -rf /etc/nginx/conf.d/*

# Copy custom enterprise Nginx reverse proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built frontend assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port 80
EXPOSE 80

# Health check to ensure nginx is serving requests
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
