FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    libssl-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv
COPY ./config.example.yaml /config/config.yaml
COPY ./pyproject.toml ./uv.lock /app/
RUN uv sync --all-groups
COPY ./microclaw/ /app/microclaw/

ENV SESSIONS_STORAGES_PATH=/data/sessions-storages

ENTRYPOINT ["uv", "run", "python", "-m", "microclaw"]
CMD ["--config", "/config/config.yaml", "run"]