FROM ghcr.io/astral-sh/uv:bookworm-slim AS builder
USER root
RUN apt-get update && apt-get install -y \
    gnome-screenshot \
    libgl1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcups2 \
    fonts-liberation \
    libappindicator3-1 \
    libgdk-pixbuf2.0-0 \
    xorg \
    x11vnc \
    xvfb \
    && apt-get clean

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Configure the Python directory so it is consistent
ENV UV_PYTHON_INSTALL_DIR=/python
# Only use the managed Python version
ENV UV_PYTHON_PREFERENCE=only-managed
# Install Python before the project for caching
RUN uv python install 3.12
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
ENV PLAYWRIGHT_BROWSERS_PATH="/opt/playwright"
RUN PLAYWRIGHT_BROWSERS_PATH="/opt/playwright" uv run playwright install && \
    ln -s /opt/playwright/chromium-*/chrome-linux/chrome /usr/bin/chromium-browser && \
    chmod -R 755 /opt/playwright
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"
# Set a default display number
ENV DISPLAY=:99
ENV QT_DEBUG_PLUGINS=1

# # Start Xvfb in the background and run your command
# CMD bash -c "Xvfb $DISPLAY -ac -screen 0 1024x768x16" & \
#     sleep 1 && \
#     uv run core/web/serve.py

WORKDIR /app/core/web
# Start Xvfb in the background and run your command
CMD bash -c "Xvfb $DISPLAY -ac -screen 0 1024x768x16" & \
    sleep 1 && \
    uv run gunicorn "serve:app" --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:9000 --threads 8
# uvicorn serve:app --host 0.0.0.0 --port 9000 --workers 1
