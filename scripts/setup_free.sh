#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_free.sh  –  Get the FREE version running in minutes
# ─────────────────────────────────────────────────────────────────────────────
# Usage:  bash scripts/setup_free.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║   HealthAI Platform – FREE Setup                ║${RESET}"
echo -e "${CYAN}║   No credit card · No paid APIs                 ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""

# ─── Step 1: Check Docker ────────────────────────────────────────────────────
echo -e "${CYAN}[1/5] Checking Docker...${RESET}"
if ! command -v docker &>/dev/null; then
    echo -e "${RED}✗  Docker not found.${RESET}"
    echo "   Install from: https://docker.com"
    exit 1
fi
echo -e "${GREEN}✓  Docker found${RESET}"

# ─── Step 2: Create .env from free template ──────────────────────────────────
echo ""
echo -e "${CYAN}[2/5] Setting up environment...${RESET}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠   .env already exists – skipping (delete it to regenerate)${RESET}"
else
    cp .env.free .env
    echo -e "${GREEN}✓  Created .env from .env.free${RESET}"
fi

# ─── Step 3: Ask user to pick provider ───────────────────────────────────────
echo ""
echo -e "${CYAN}[3/5] Choose your FREE LLM provider:${RESET}"
echo ""
echo "  A) Groq  – Fastest ⚡ Free cloud API, no credit card"
echo "             Sign up at: https://console.groq.com"
echo "             (takes 2 min, just email + password)"
echo ""
echo "  B) Ollama – Fully offline 🔒 No account needed"
echo "              Needs: 4GB free RAM, install from ollama.com"
echo ""
echo "  C) Skip  – I'll configure it manually in .env"
echo ""
read -rp "  Your choice [A/B/C]: " choice

case "${choice^^}" in
    A)
        echo ""
        echo -e "${YELLOW}Get your FREE Groq API key:${RESET}"
        echo "  1. Go to https://console.groq.com"
        echo "  2. Sign up (email + password, no credit card)"
        echo "  3. Click 'API Keys' → 'Create API Key'"
        echo "  4. Paste it below:"
        echo ""
        read -rp "  Groq API Key (starts with gsk_): " groq_key
        if [[ "$groq_key" == gsk_* ]]; then
            sed -i "s|GROQ_API_KEY=.*|GROQ_API_KEY=${groq_key}|" .env
            sed -i "s|FREE_LLM_PROVIDER=.*|FREE_LLM_PROVIDER=groq|" .env
            echo -e "${GREEN}✓  Groq key saved${RESET}"
        else
            echo -e "${YELLOW}⚠   Key doesn't look right, saved anyway – check .env${RESET}"
            sed -i "s|GROQ_API_KEY=.*|GROQ_API_KEY=${groq_key}|" .env
        fi
        ;;
    B)
        sed -i "s|FREE_LLM_PROVIDER=.*|FREE_LLM_PROVIDER=ollama|" .env
        echo ""
        echo -e "${CYAN}Ollama setup:${RESET}"
        if command -v ollama &>/dev/null; then
            echo -e "${GREEN}✓  Ollama already installed${RESET}"
            echo "   Pulling llama3.2 model (~2GB, takes a few minutes)..."
            ollama pull llama3.2 && echo -e "${GREEN}✓  Model ready${RESET}"
        else
            echo -e "${YELLOW}→  Ollama not installed on this machine.${RESET}"
            echo "   It will run inside Docker automatically."
            echo "   After startup, pull the model with:"
            echo "   docker compose -f docker-compose.free.yml exec ollama ollama pull llama3.2"
        fi
        ;;
    *)
        echo -e "${YELLOW}⚠   Skipped – edit .env manually before starting${RESET}"
        ;;
esac

# ─── Step 4: Generate a secure SECRET_KEY ────────────────────────────────────
echo ""
echo -e "${CYAN}[4/5] Generating secure SECRET_KEY...${RESET}"
if command -v openssl &>/dev/null; then
    NEW_KEY=$(openssl rand -hex 32)
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=${NEW_KEY}|" .env
    echo -e "${GREEN}✓  SECRET_KEY generated${RESET}"
else
    echo -e "${YELLOW}⚠   openssl not found – using default key (change for production!)${RESET}"
fi

# ─── Step 5: Start the platform ──────────────────────────────────────────────
echo ""
echo -e "${CYAN}[5/5] Starting the platform...${RESET}"
echo ""
echo "  This will:"
echo "  • Build Docker images (~5 min first time)"
echo "  • Start 16 containers (Kafka, Redis, Qdrant, 8 services, frontend...)"
echo "  • Download embedding model ~90MB on first run (cached after)"
echo ""
read -rp "  Start now? [Y/n]: " confirm
if [[ "${confirm^^}" == "N" ]]; then
    echo ""
    echo "  When ready, run:"
    echo -e "  ${CYAN}docker compose -f docker-compose.free.yml up --build${RESET}"
    echo ""
    exit 0
fi

echo ""
docker compose -f docker-compose.free.yml up --build -d

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║   Platform is starting!                         ║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""
echo "  Waiting 30s for services to initialize..."
sleep 30
echo ""
echo "  Check health:"
echo -e "  ${CYAN}bash scripts/healthcheck.sh${RESET}"
echo ""
echo "  Then seed demo data:"
echo -e "  ${CYAN}python scripts/seed_demo.py${RESET}"
echo ""
echo -e "  ${GREEN}Open:  http://localhost:3000${RESET}  (login: demo_user / demo)"
echo -e "  ${GREEN}API:   http://localhost:8000/docs${RESET}"
echo -e "  ${GREEN}LLM:   http://localhost:8006/providers${RESET}  (see provider status)"
echo ""
