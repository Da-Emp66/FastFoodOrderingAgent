# Use GitHub Container Registry mirror to avoid Docker Hub rate limits
# FROM ghcr.io/nodejs/node:22-alpine
FROM node:22-alpine

WORKDIR /app

# Copy package files first for better Docker layer caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the application
RUN npm run build

EXPOSE 3000

CMD [ "npm", "run", "serve" ]