# app/Dockerfile

FROM python:3.12-slim-bookworm

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.7.13 /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
	build-essential \
	curl \
	software-properties-common \
	git \
	&& rm -rf /var/lib/apt/lists/*

COPY . .

RUN uv sync

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]



