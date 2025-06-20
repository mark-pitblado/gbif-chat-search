FROM python:3.12-slim-bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install UV
COPY --from=ghcr.io/astral-sh/uv:0.7.13 /uv /uvx /bin/

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Configure UV
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Production stage
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Create non-root user
RUN groupadd -r app && useradd -r -d /app -g app -N app

# Copy UV and virtual environment from builder
COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set proper ownership and switch to non-root user
RUN chown -R app:app /app
USER app

# Add .venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8501

# Improved healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail --silent --show-error http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
