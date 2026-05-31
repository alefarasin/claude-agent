# Claude Agent 🤖

Bot Telegram che esegue istruzioni in linguaggio naturale sul tuo repository usando Claude Code CLI.

## Setup rapido

### 1. Clona il repo
```bash
git clone https://github.com/TUO-USERNAME/claude-agent.git
cd claude-agent
```

### 2. Configura le variabili d'ambiente
```bash
cp .env.example .env
# Modifica .env con i tuoi valori
```

### 3. Lancia con Docker
```bash
docker compose up -d
```

## Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/start` | Avvia il bot |
| `/status` | Stato del workspace |
| `/log` | Ultimi 5 commit |
| `/help` | Guida rapida |

Oppure invia qualsiasi istruzione in linguaggio naturale:
- `Crea una funzione fibonacci con i test`
- `Fai il refactoring di main.py`
- `Aggiungi la documentazione a tutte le funzioni`

## Requisiti

- Docker + Docker Compose
- Account Anthropic (piano Pro o API key)
- Bot Telegram (via @BotFather)
- GitHub Personal Access Token

## Portabilità

Il container gira identico su:
- Laptop (Mac/Linux/Windows con Docker Desktop)
- VPS (Hetzner, DigitalOcean, ecc.)
- Qualsiasi macchina con Docker installato
