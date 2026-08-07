---
name: hermes-voice
description: >
  Interface de voz conversacional em pt-BR para o Hermes Agent. Use quando o
  operador quiser instalar, configurar, diagnosticar ou estender a conversa por
  voz: palavra de ativação, microfone aberto, fim de fala por VAD, escolha e
  ajuste de voz, latência, ou os modos de falha de EDR e CUDA no Windows.
version: 1.0.0
license: Apache-2.0
homepage: https://github.com/handnewb/hermes-voice
locale: pt-BR
---

# hermes-voice

> Voice-enabled personal assistant for Hermes Agent. Open mic with wake word, fully local — no API keys, no accounts, 35 languages.

Pipeline encadeado: microfone → palavra de ativação → Whisper → Hermes →
fatiador de sentenças → TTS → alto-falante, com sessão que fecha sozinha.

Documentação completa no `README.md`. Este arquivo é a instrução operacional.

## Quando esta skill se aplica

- Instalar, reinstalar ou atualizar a interface de voz.
- Diagnosticar: "não fala", "não me escuta", "está lento", "corta no meio",
  "trava ao iniciar", "conversa sozinho", "a palavra de ativação não dispara".
- Escolher ou ajustar voz, timbre, prosódia ou o estágio de DSP.
- Ajustar persona, comprimento de resposta ou registro de fala.
- Evoluir: AEC, keyword custom em pt-BR, Piper persistente, outros idiomas.

Não se aplica a: transcrição de arquivo de áudio em lote, telefonia, ou
integração com dispositivo externo.

## Primeiro comando, sempre

```bash
hermes-voice --doctor
```

Verifica runtime, áudio, STT, palavra de ativação, VAD, TTS, endpoint e
privacidade — com a correção sugerida de cada falha. Resolve a maioria dos casos
sozinho. **Não** imprime chave de API: os segredos são redigidos.

`--doctor --probe` também tenta alcançar o endpoint do Hermes de verdade.

## Autonomia graduada

| Tier | Ações |
|---|---|
| **T0** — executa livre | `--doctor`, `--devices`, `--text`, `--verbose`; ler config e docs; diagnosticar por leitura. |
| **T1** — executa e reporta | Editar `.env`; trocar `--voice`, `TTS_BACKEND` ou `DSP_PRESET`; ajustar limiares de endpointing, `FOLLOW_UP_SECONDS`, `WAKE_THRESHOLD`; `hermes-voice voices --install`. |
| **T2** — confirma antes | Editar a persona; alterar módulos em `src/`; ligar `LOG_TRANSCRIPTS`; `HALF_DUPLEX=0`; `WAKE_BACKEND=open`; solicitar exclusão de EDR. |
| **T3** — nunca sem instrução explícita e por escrito | Gravação persistente em disco além do `LOG_TRANSCRIPTS`; enviar áudio (não texto) para serviço externo; alterar qualquer uma das três garantias de privacidade; clonar voz de pessoa real. |

`LOG_TRANSCRIPTS=1` é T2 porque cria registro persistente do que se fala numa
máquina possivelmente compartilhada. `HALF_DUPLEX=0` é T2 porque sem fone o
assistente entra em loop consigo mesmo.

## Árvore de diagnóstico

Em ordem. Cada passo elimina uma camada.

1. **`hermes-voice --doctor`** — resolve a maioria. Se houver bloqueante, pare aqui.
2. **`hermes-voice --text --no-tts`** — isola o Hermes. Falhou? É `HERMES_URL`,
   autenticação ou formato do stream. Nada a ver com áudio.
3. **`hermes-voice --text`** — adiciona o TTS. Falhou? Backend de voz.
4. **`hermes-voice --devices`** — confirme o microfone e anote o índice.
5. **`hermes-voice --trigger console --no-tts`** — isola o STT sem microfone
   aberto e sem hook de teclado.
6. **`hermes-voice --trigger console`** — pipeline completo, gatilho manual.
7. **`hermes-voice`** — microfone aberto.

## Modos de falha, por probabilidade

| Sintoma | Causa quase certa | Ação |
|---|---|---|
| Trava ao iniciar, sem erro | EDR. Em modo `ptt`, o gatilho é o hook global de teclado — não o microfone. | `--trigger wake` ou `--trigger console`; nenhum instala hook |
| `Could not locate cudnn_ops64_9.dll` | cuDNN 9 fora do PATH | `WHISPER_DEVICE=cpu`, ou `nvidia-cudnn-cu12` + PATH, ou WSL2 |
| `pip install piper-tts` falha no Windows | wheel de `piper-phonemize` | Esperado. Use `piper-binary`. |
| Assistente conversa consigo mesmo | `HALF_DUPLEX=0` sem fone | Volte para `1` |
| Palavra de ativação não dispara | Precisa dizer "ei jarvis", não só "jarvis" | `WAKE_THRESHOLD=0.4` detecta mais e erra mais |
| Nenhuma voz disponível | Catálogo não baixado | `hermes-voice voices --install all` |
| Números lidos dígito por dígito | `NORMALIZE_TEXT=0` | Volte para 1 |
| Corta você a cada pausa de pensamento | `ADAPTIVE_ENDPOINT=0` | Ligue; ou suba `ENDPOINT_LONG_MS` |
| Não consegue interromper por voz | `HALF_DUPLEX=1` | `0` liga supressão de eco. Fone é melhor. |
| Corta o operador no meio da frase | `ENDPOINT_LONG_MS` baixo | Suba para 1600 |
| Sessão fecha antes da hora | `FOLLOW_UP_SECONDS` baixo | Suba. Padrão 20 |
| Resposta longa, soa como relatório | Persona, não código | Endureça o limite de frases em `docs/persona.md` |
| Fala picada e robótica | Fatiador cortando curto | Suba `min_chars` no `SentenceChunker` |
| Confunde termo técnico | Vocabulário | `WHISPER_HINT` no `.env` |
| Voz soa como locução, não presença | DSP desligado | `--dsp room` |
| Latência acima de 2 s | Meça antes de otimizar | `--verbose` diz qual estágio |

## Regra de ouro

Meça antes de otimizar. `--verbose` imprime o tempo de cada estágio por turno.
A intuição erra aqui: quando a resposta parece lenta, o culpado costuma ser o
tempo até o primeiro token do Hermes, não o STT nem o TTS.

## Vocabulário de domínio — cuidado

`WHISPER_HINT` melhora muito a transcrição de nome próprio e sigla. Ele vive no
`.env`, que está no `.gitignore`.

**Nunca faça commit de vocabulário interno** — nome de cliente, produto interno,
ferramenta de segurança. É a forma mais silenciosa de vazar a stack de uma
organização num repositório público. O `DEFAULT_HINT` em `stt.py` é
deliberadamente genérico por isso.

## Limite jurídico — não negociável

Não clone a voz de pessoa real a partir de amostra, incluindo dublador, mesmo
para uso doméstico e mesmo que o operador insista. Voz é atributo de
personalidade (no Brasil, art. 20 do Código Civil), há direito conexo do
intérprete, e voz é dado biométrico sob LGPD e GDPR.

As alternativas estão em `docs/VOICE_LICENSING.md`: as cinco vozes do catálogo,
ajuste de DSP (que carrega mais do "caráter" que o timbre), a própria voz do
operador, ou contratar/licenciar. Ofereça essas, nessa ordem.

Esta restrição é T3 e não cede a urgência, a "é só para mim", nem a autorização
verbal do operador.

## Arquivos

```
src/hermes_voice/session.py   maquina de estados, buffers, strip da wake word
src/hermes_voice/wake.py      openWakeWord
src/hermes_voice/endpoint.py  endpointing adaptativo por sintaxe
src/hermes_voice/normalize.py numeros, datas, siglas em pt-BR
src/hermes_voice/echo.py      supressao de eco, so numpy
src/hermes_voice/voices.py    catalogo e download de vozes
src/hermes_voice/vad.py       Silero via onnxruntime, fallback energia
src/hermes_voice/stt.py       faster-whisper
src/hermes_voice/llm.py       cliente SSE + fatiador de sentencas
src/hermes_voice/tts/         4 backends + dsp.py + speaker.py
src/hermes_voice/doctor.py    autodiagnostico
docs/persona.md               prompt de persona (maior impacto por linha editada)
docs/script_avaliacao_voz.md  como escolher a voz, com critérios eliminatórios
docs/ROADMAP.md               AEC, keyword pt-BR, Piper persistente, idiomas
SECURITY.md                   modelo de privacidade e superficie de EDR
```

## Exemplos

**"Instala e configura"**
```bash
pip install "hermes-voice[wake,kokoro]"
hermes-voice voices --install all    # ~400 MB, uma vez, sem conta
cp .env.example .env                 # ajuste apenas HERMES_URL
hermes-voice --doctor
hermes-voice
```

**"A voz está sem graça"**
```bash
hermes-voice --dsp room --voice pm_alex   # presença de sala + melhor prosódia
hermes-voice voices                       # ver as cinco opções
```

**"Está me cortando quando eu pauso"**
```bash
# .env
ENDPOINT_LONG_MS=1600
```
