FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:/root/.cargo/bin:$PATH"

RUN apt-get update && apt-get install -y \
    bash \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    nodejs \
    npm \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY . .

RUN chmod +x scripts/dev_start.sh

ENTRYPOINT ["./scripts/dev_start.sh"]
