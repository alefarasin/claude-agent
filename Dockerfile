FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"

# Base deps + C/C++ + Rust toolchain
RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip python3-venv \
    build-essential sudo unzip wget ca-certificates \
    cmake clang lld libssl-dev pkg-config gdb \
    rustc cargo rustfmt \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 (richiesto da Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Utente non-root con sudo illimitato (necessario per --dangerously-skip-permissions)
RUN useradd -m -s /bin/bash claude \
    && echo "claude ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/claude \
    && chmod 0440 /etc/sudoers.d/claude

USER claude
WORKDIR /home/claude

# Layer 1: dipendenze (cached finché pyproject.toml/poetry.lock non cambiano)
COPY --chown=claude:claude pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# Layer 2: sorgenti + installazione del progetto
COPY --chown=claude:claude . .
RUN poetry install --only main && chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
