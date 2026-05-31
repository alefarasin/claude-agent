FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Dipendenze base
RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip python3-venv \
    build-essential sudo unzip wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 (richiesto da Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Utente non-root
RUN useradd -m -s /bin/bash claude && \
    echo "claude ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER claude
WORKDIR /home/claude

# Python virtualenv e dipendenze bot
RUN python3 -m venv /home/claude/venv
COPY --chown=claude:claude requirements.txt .
RUN /home/claude/venv/bin/pip install --upgrade pip && \
    /home/claude/venv/bin/pip install -r requirements.txt

# Copia il bot
COPY --chown=claude:claude bot.py .
COPY --chown=claude:claude entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]