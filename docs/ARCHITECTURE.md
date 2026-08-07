# Arquitetura

## O pipeline

```
microfone (sempre aberto, frames de 32 ms)
   │
   ├── DORMANT ──► wake.py ────────────────► nada é transcrito aqui
   │                  │ dispara
   ├── LISTENING ──► vad.py ──► fim de fala ──► session.take()
   │                                              │
   │                              stt.py (faster-whisper)
   │                                              │
   │                              llm.py ──► SentenceChunker
   │                                              │ frase por frase
   │                              tts/ ──► dsp.py ──► speaker.py ──► saída
   │                                                      │
   └── SPEAKING ◄────────────────────────────────────────┘
```

## As três decisões que definem o resto

**1. Pipeline encadeado, não speech-to-speech.** Não existe modelo S2S local
decente em pt-BR hoje. É escolha correta, não compromisso — e permite trocar
qualquer estágio isoladamente. Reavaliar quando houver S2S multilíngue local.

**2. Fatiamento por sentença em vez de esperar a resposta completa.** É a única
otimização de latência que muda a ordem de grandeza. As outras são marginais.

**3. Máquina de estados como fonte única de verdade sobre o áudio.** Toda decisão
de "o que fazer com este frame" está em `loops.run_wake_mode`, consultando
`session.state`. Sem isso, as regras de privacidade ficam espalhadas por três
módulos e ninguém consegue auditar.

## Por que os imports de áudio são preguiçosos

`sounddevice` carrega `libportaudio` no import. Runner de CI e container não têm
placa de som. Se o import fosse no topo, o pacote seria inimportável em CI e a
suíte de testes não existiria — que é o destino da maioria dos projetos de áudio.

`audio._sd()` resolve isso: o pacote importa em qualquer lugar, e o PortAudio só
é exigido quando alguém realmente vai capturar ou tocar áudio.

## Contratos entre módulos

| Fronteira | Contrato |
|---|---|
| `audio.FrameSource` → loop | `np.float32`, mono, 512 amostras, fila limitada que descarta o antigo |
| loop → `wake.FrameAdapter` | `int16`; o adaptador reagrupa para o que o backend exige (512 no Porcupine, 1280 no openWakeWord) |
| loop → `vad` | `float32`, exatamente 512 amostras (exigência do Silero v5) |
| `session.take()` → `stt` | `float32` mono 16 kHz concatenado, mais o pico de amplitude |
| `llm.stream()` → `SentenceChunker` | deltas de texto de tamanho arbitrário |
| `SentenceChunker` → `tts` | trechos falantes, sem markdown |
| backend `tts` → `speaker` | PCM `int16` little-endian em pedaços de tamanho arbitrário |

O contrato do `SentenceChunker` tem uma propriedade testada explicitamente: **o
resultado não pode depender de como o stream fatia os deltas.** Deltas de 1 a 23
caracteres precisam produzir saída idêntica. Sem isso o áudio muda conforme a
velocidade da rede.

## Estado, e onde ele mora

Quatro lugares guardam estado mutável. Todos os outros módulos são sem estado.

- `session.Session` — estado da conversa, pré-roll, buffer de fala
- `vad.SpeechGate` — histerese de fala/silêncio
- `tts.dsp.Presence` — filtros biquad, envelope do compressor, linha de delay
- `llm.HermesClient` — histórico da conversa

Os três primeiros têm `reset()`, e há teste verificando que `reset()` zera tudo —
inclusive os biquads, cujo esquecimento fazia resto da frase anterior sangrar na
seguinte.

## Onde tocar para estender

| Objetivo | Arquivo | Nota |
|---|---|---|
| Novo backend de TTS | `tts/`, mais uma entrada em `_make()` | Implemente `synth()` e `close()` |
| Novo detector de wake word | `wake.py` | `FrameAdapter` cuida do tamanho de frame |
| Trocar o STT | `stt.py` | Contrato: `float32` 16 kHz → `str` |
| Novo idioma | `docs/persona.md`, `DEFAULT_HINT`, regex em `session.py`, `ABBREVIATIONS` em `llm.py` | São os quatro únicos pontos |
| AEC | `audio.py` (loopback) e o ramo `SPEAKING` em `loops.py` | Ver ROADMAP; é o item difícil |
