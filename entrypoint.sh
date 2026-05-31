#!/bin/bash
set -e

echo "🚀 Claude Agent avvio..."

# Configura git globalmente
git config --global user.email "claude-agent@bot.local"
git config --global user.name "Claude Agent"
git config --global credential.helper store

# Salva credenziali git
echo "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com" > ~/.git-credentials

echo "✅ Configurazione completata"
echo "🤖 Avvio bot Telegram..."

# Avvia il bot
exec /home/claude/venv/bin/python bot.py
