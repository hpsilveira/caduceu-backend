# Use the official Python image as a parent image
FROM python:3.14.6-slim-trixie

# Install git
RUN apt-get update && apt-get install -y \
    git \
    gh \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application
RUN groupadd --gid 1000 fastapi \
    && useradd --uid 1000 --gid fastapi --shell /bin/bash --create-home fastapi

# Set user
USER fastapi

# Expose the port the app runs on
EXPOSE 8000
