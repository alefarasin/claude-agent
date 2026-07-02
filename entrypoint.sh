#!/bin/bash
set -e

echo "🚀 Claude Agent avvio..."

# Configura git globalmente
git config --global user.email "claude-agent@bot.local"
git config --global user.name "Claude Agent"
git config --global credential.helper store

# Salva credenziali git
echo "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com" > ~/.git-credentials

# Verifica che il token OAuth sia presente
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN}" ]; then
    echo "❌ CLAUDE_CODE_OAUTH_TOKEN non impostato."
    echo "   Generalo con: docker compose run --rm claude-agent claude setup-token"
    echo "   Poi incollalo nel file .env"
    exit 1
fi

# Assicura che il volume workspace sia scrivibile dall'utente corrente
sudo chown claude:claude /home/claude/workspace 2>/dev/null || true

echo "✅ Configurazione completata"
echo "🤖 Avvio bot Telegram..."

exec poetry run claude-agent
