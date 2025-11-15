FROM nvidia/cuda:13.0.2-base-ubuntu22.04
USER root
# RUN apt-get update && apt-get install libgl1 libglib2.0-0 -y && apt-get clean
RUN apt-get update && \
    apt-get install libgl1 libglib2.0-0 -y && \
    apt-get install python3.10-venv python3-pip -y && \
    apt-get clean && \
    pip install uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Configure the Python directory so it is consistent
ENV UV_PYTHON_INSTALL_DIR=/python
# Only use the managed Python version
ENV UV_PYTHON_PREFERENCE=only-managed
# Install Python before the project for caching
RUN uv python install 3.10
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"
CMD [ "uv", "run", "omnitool/omniparserserver/omniparserserver.py" ]
