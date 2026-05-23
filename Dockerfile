FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Dipendenze base
RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip \
    build-essential sudo unzip wget \
    && rm -rf /var/lib/apt/lists/*

# Node.js (richiesto da Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Utente non-root
RUN useradd -m -s /bin/bash claude && \
    echo "claude ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER claude
WORKDIR /home/claude

CMD ["bash"]
EOF