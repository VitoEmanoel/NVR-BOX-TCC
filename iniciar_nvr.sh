#!/bin/bash

set -e

DIRETORIO_ATUAL="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$DIRETORIO_ATUAL/.run"

mkdir -p "$RUN_DIR"
cd "$DIRETORIO_ATUAL"

parar_processo() {
    local nome="$1"
    local pid_file="$RUN_DIR/$nome.pid"

    if [ ! -f "$pid_file" ]; then
        return
    fi

    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
        echo "Parando $nome anterior (PID $pid)..."
        kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
}

encerrar_todos() {
    parar_processo servidor
    parar_processo captura
    parar_processo limpeza
}

trap encerrar_todos EXIT INT TERM

iniciar_com_log() {
    local nome="$1"
    local log="$RUN_DIR/$nome.log"
    if [ -f "$log" ] && [ "$(wc -c < "$log")" -gt 5242880 ]; then
        mv -f "$log" "$log.antigo"
    fi
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') iniciando $nome ===" >> "$log"
    python3 -u -m "nvrbox.$nome" >> "$log" 2>&1 &
    echo "$!" > "$RUN_DIR/$nome.pid"
}

echo "Limpando instancias anteriores do NVRBox..."
encerrar_todos

echo "Iniciando NVRBox no diretorio: $DIRETORIO_ATUAL"

echo "-> [1/3] Ativando script de Limpeza Automatica..."
iniciar_com_log limpeza

echo "-> [2/3] Ativando motor de Captura FFmpeg..."
iniciar_com_log captura

echo "-> [3/3] Abrindo Painel Web... Sistema ONLINE!"
iniciar_com_log servidor

wait "$(cat "$RUN_DIR/servidor.pid")"
