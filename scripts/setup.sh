#!/usr/bin/env bash
# Prepara o ambiente do hermes-voice em Linux e macOS.
# Uso: ./scripts/setup.sh [--cpu] [--skip-piper]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CPU=0; SKIP_PIPER=0
for arg in "$@"; do
  case "$arg" in
    --cpu) CPU=1 ;;
    --skip-piper) SKIP_PIPER=1 ;;
    *) echo "argumento desconhecido: $arg" >&2; exit 1 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    + %s\n' "$1"; }
warn() { printf '    ! %s\n' "$1"; }

step "Verificando Python"
command -v python3 >/dev/null || { echo "python3 nao encontrado" >&2; exit 1; }
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
ok "Python $PYV"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || { echo "Python 3.10+ necessario" >&2; exit 1; }

step "Dependencias de sistema"
if [[ "$(uname)" == "Darwin" ]]; then
  command -v brew >/dev/null && brew list portaudio >/dev/null 2>&1 \
    && ok "portaudio presente" || warn "brew install portaudio"
else
  ldconfig -p 2>/dev/null | grep -q libportaudio \
    && ok "libportaudio presente" \
    || warn "sudo apt install libportaudio2   (ou o equivalente da sua distro)"
fi

step "Ambiente virtual"
[[ -d .venv ]] || python3 -m venv .venv
ok ".venv pronto"
VPY="$ROOT/.venv/bin/python"

step "Instalando o pacote"
"$VPY" -m pip install --upgrade pip --quiet
"$VPY" -m pip install -e ".[wake,ptt,piper,dev]"
ok "instalado em modo editavel"

if [[ "$SKIP_PIPER" -eq 0 ]]; then
  step "Piper: binario e voz pt-BR"
  mkdir -p bin voices
  if [[ ! -x bin/piper/piper ]]; then
    case "$(uname -s)-$(uname -m)" in
      Linux-x86_64)  ASSET=piper_linux_x86_64.tar.gz ;;
      Linux-aarch64) ASSET=piper_linux_aarch64.tar.gz ;;
      Darwin-arm64)  ASSET=piper_macos_aarch64.tar.gz ;;
      Darwin-x86_64) ASSET=piper_macos_x64.tar.gz ;;
      *) ASSET="" ; warn "plataforma sem binario pronto; use o backend piper-python" ;;
    esac
    if [[ -n "$ASSET" ]]; then
      URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/$ASSET"
      echo "    baixando $ASSET"
      curl -fsSL "$URL" | tar -xz -C bin
      ok "bin/piper/piper"
    fi
  else
    ok "binario ja presente"
  fi

  BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium"
  for f in pt_BR-faber-medium.onnx pt_BR-faber-medium.onnx.json; do
    if [[ -f "voices/$f" ]]; then ok "$f ja presente"; else
      echo "    baixando $f"; curl -fsSL -o "voices/$f" "$BASE/$f"; ok "$f"
    fi
  done
fi

step "Configuracao"
if [[ -f .env ]]; then ok ".env ja existe; nao foi tocado"; else
  cp .env.example .env; ok ".env criado"
fi
if [[ "$CPU" -eq 1 ]]; then
  sed -i.bak 's/^WHISPER_DEVICE=cuda/WHISPER_DEVICE=cpu/; s/^WHISPER_COMPUTE=int8_float16/WHISPER_COMPUTE=int8/' .env
  rm -f .env.bak; ok "Whisper em CPU"
fi
if [[ "$(uname)" != "Darwin" ]]; then
  sed -i.bak 's|^PIPER_BINARY=bin/piper/piper.exe.*|PIPER_BINARY=bin/piper/piper|' .env
  rm -f .env.bak
fi

step "Pendencias"
warn "PICOVOICE_ACCESS_KEY no .env -- gratuita em console.picovoice.ai"
warn "HERMES_URL no .env -- endpoint compativel com /v1/chat/completions em streaming"
warn "Sem AEC nesta versao: use fone, ou mantenha HALF_DUPLEX=1"

step "Proximos passos"
cat <<'NEXT'
    source .venv/bin/activate
    hermes-voice --doctor      # diz exatamente o que ainda falta
    hermes-voice --text        # valida Hermes + voz sem microfone
    hermes-voice               # microfone aberto
NEXT
