#!/bin/bash
# Inicia o backend e o frontend do affiliate-agents

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

case "${1:-all}" in
  backend|back|b)
    echo "🚀 Iniciando backend..."
    source venv/bin/activate
    PYTHONPATH=. uvicorn backend.server:app --host 0.0.0.0 --port 8000 \
      --reload \
      --reload-dir backend --reload-dir graph --reload-dir agents --reload-dir services \
      --reload-exclude '__pycache__' \
      --timeout-keep-alive 0
    ;;
  frontend|front|f)
    echo "🚀 Iniciando frontend..."
    cd frontend && npm run dev
    ;;
  all|a)
    echo "🚀 Iniciando backend + frontend..."

    # Mata processos anteriores nas portas
    lsof -ti:8000 -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null
    sleep 1

    source venv/bin/activate

    # Cleanup ao sair (Ctrl+C, kill, etc.)
    cleanup() {
      echo ""
      echo "🛑 Parando processos..."
      kill "$BACKEND_PID" 2>/dev/null
      wait "$BACKEND_PID" 2>/dev/null
    }
    trap cleanup EXIT INT TERM

    PYTHONPATH=. uvicorn backend.server:app --host 0.0.0.0 --port 8000 \
      --timeout-keep-alive 0 &
    BACKEND_PID=$!

    # Aguarda o backend estar pronto antes de iniciar o frontend
    echo "⏳ Aguardando backend na porta 8000..."
    for i in $(seq 1 30); do
      if curl -s http://localhost:8000/agent/status > /dev/null 2>&1; then
        echo "✅ Backend pronto!"
        break
      fi
      sleep 1
    done

    cd frontend && npm run dev
    ;;
  *)
    echo "Uso: ./run.sh [backend|frontend|all]"
    echo "  backend (back, b)  — só o backend na porta 8000"
    echo "  frontend (front, f) — só o frontend na porta 3000"
    echo "  all (a)            — ambos (padrão)"
    ;;
esac
