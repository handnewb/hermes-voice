# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.1] — 2026-08-07

### Corrigido

- **Backend `auto` no Windows:** prefere `piper-binary` antes de `kokoro`
  porque o espeak-ng frequentemente não tem dados do idioma, e `piper-python`
  não compila em Windows. Antes o `auto` tentava Kokoro → piper-python →
  piper-binary, e as duas primeiras falhavam silenciosamente.
- **Lint:** imports `os` e `pathlib.Path` fora de lugar em `tts/__init__.py`.

### Verificado

- **Jarvis** (Windows 11, RTX 4060, Python 3.13): 229 testes ✅, lint ✅,
  doctor 8/8 ✅, GPU CUDA ✅, 11 microfones ✅, Piper binary TTS ✅, DSP
  room ✅, endpoint HTTP 200 ✅, pipeline completo LLM+TTS+DSP a 1573ms.
- **Mestre** (Linux 6.8, Python 3.11): 229 testes ✅, lint ✅, format ✅.

### Conhecido

- Kokoro + espeak-ng no Windows: `TTS_BACKEND=piper-binary`.
- Wake word e microfone aberto não testados via SSH remoto.

---

## [1.0.0] — 2026-08-06

Primeira versão pública.

### Adicionado

- **Conversa contínua** com microfone aberto. A palavra de ativação abre uma
  sessão; dentro dela você fala sem repeti-la. A sessão fecha sozinha após
  `FOLLOW_UP_SECONDS` sem fala. Máquina de estados em `session.py`.
- **Três modos de gatilho**: `wake` (microfone aberto), `console` (ENTER, sem
  hook de teclado) e `ptt` (segure uma tecla).
- **Palavra de ativação** via Porcupine, onde `jarvis` é keyword nativa — zero
  treinamento. Fallback para openWakeWord.
- **Fim de fala** por Silero VAD via onnxruntime, sem torch. Histerese
  deliberada: entra em fala rápido, sai devagar, para não cortar pausa natural.
  Fallback por energia quando o modelo não está disponível.
- **STT** com faster-whisper, vocabulário de domínio configurável e queda
  automática para CPU quando CUDA falha.
- **Quatro backends de TTS**: ElevenLabs, Azure Speech, Piper (Python) e Piper
  (binário), com seleção automática por ordem de qualidade.
- **Estágio de DSP de presença**: high-pass, compressor, realce de presença e
  reverb curto de sala. Cinco presets. Faz a voz soar como som na sala em vez de
  locução, que é a metade da experiência que nenhum TTS entrega.
- **Fatiador de sentenças** que envia a primeira frase ao TTS enquanto o modelo
  ainda gera a segunda. Corta 60–70% da latência percebida.
- **`--doctor`**: diagnostica runtime, áudio, STT, palavra de ativação, VAD, TTS,
  endpoint e privacidade, com correção sugerida para cada falha.
- **Script de avaliação de voz** anotado, com critérios eliminatórios, e um
  monólogo de 1.031 palavras para teste de estabilidade long-form.
- Suíte de 128 testes que não exige placa de som, GPU, rede nem chave de API.
- CI em Linux, Windows e macOS × Python 3.10–3.13. CodeQL e Gitleaks.

### Segurança

- Pré-roll limitado por construção (`deque` com `maxlen`), não por configuração.
  Testado com 64 s de áudio contínuo.
- Nada é transcrito em estado `DORMANT`.
- `Config.redacted()` para log e diagnóstico, com teste que falha se um segredo
  conhecido aparecer na saída.
- `LOG_TRANSCRIPTS=0` por padrão.

### Notas

- **Não** inclui clonagem de voz, por decisão de projeto. Ver `CONTRIBUTING.md`.
- AEC não implementado: no modo `wake`, `HALF_DUPLEX=1` (padrão) evita que o
  assistente escute a própria voz. Para conversar com caixas abertas, ver
  `docs/ROADMAP.md`.
