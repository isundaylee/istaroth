# Multi-stage build for React frontend
ARG NODE_VERSION=18
FROM node:${NODE_VERSION}-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies (including dev dependencies needed for build)
RUN npm ci

# Copy source code
COPY . .

# Lint and build the application
RUN npm run lint && npm run build

# Production stage with unprivileged nginx
FROM nginxinc/nginx-unprivileged:alpine

# Copy built assets from builder stage
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 8080 (default for unprivileged nginx)
EXPOSE 8080

# Start nginx (runs as nginx user by default)
CMD ["nginx", "-g", "daemon off;"]
