## Build stage
FROM node:20-alpine AS build
WORKDIR /app
# Copy only package files first to leverage Docker layer caching
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit --progress=false || npm install
COPY . .
# Allow overriding API base at build time
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

## Runtime stage (Nginx)
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
