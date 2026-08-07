# Status de verificação

Este documento existe porque a diferença entre "escrito" e "verificado" costuma
ficar implícita, e num projeto que grava áudio e baixa modelos essa diferença
importa. Abaixo está o que foi executado, o que não foi, e onde eu apostaria que
há problema.

Escrito antes da primeira publicação. Atualize junto com as correções.

---

## Verificado por teste automatizado

229 testes, executados repetidamente. Nenhum exige placa de som, GPU, rede ou
chave de API.

| Componente | O que foi verificado |
|---|---|
| `llm.SentenceChunker` | Resultado idêntico para deltas de 1 a 23 caracteres; nenhum caractere perdido; `12:30`, `4.812`, `Dr.` preservados; emite antes do fim do stream |
| `session.Session` | Ciclo completo de estados; pré-roll limitado a 480 ms após 64 s de áudio; buffer descartado ao adormecer, inclusive quando já dormia |
| `session.strip_wake_word` | 7 variantes removidas; 9 palavras legítimas preservadas, incluindo "Gervásio" e "Java" |
| `tts.dsp.Presence` | −12,5 dB em 80 Hz medido por FFT; continuidade de estado com erro ≤ 1 LSB em blocos de 2 a 4096 bytes; chunk ímpar nunca gera byte solto; compressor reduz dinâmica de 18× para 6,1×; saída nunca satura |
| `echo.EchoSuppressor` | Zero falsos positivos com eco puro em 4 atrasos (20–300 ms) × 4 ganhos de sala (0,25–1,3); dispara com fala sobreposta alta |
| `normalize` | Cardinais até milhões; moeda, data, hora, percentual, ordinal, decimal com vírgula e com ponto; idempotência; nenhum dígito remanescente |
| `endpoint` | Classificação de 15 casos; histerese; destrava com texto estagnado; teto de sondagens |
| `wake.matches` | Apelidos aceitos, colisões rejeitadas, tolerância limitada a 1 |
| `config` | Redação de segredo com teste que injeta valor conhecido; `.env` não sobrescreve ambiente; extração da persona por `rsplit` |
| Empacotamento | Wheel constrói, instala em venv limpo, entry point executa, persona viaja dentro do pacote |

---

## Verificado em hardware real (2026-08-07)

### Jarvis — Windows 11, NVIDIA RTX 4060, Python 3.13.13

| Componente | Resultado |
|---|---|
| **Instalação** | `pip install -e ".[dev,wake,kokoro]"` — sucesso |
| **Tests** | 229/229 passed em 1.55s |
| **Ruff lint** | All checks passed |
| **Ruff format** | 48 files already formatted |
| **Doctor** | Todos os 8 grupos verdes (Runtime, Audio, STT, Wake, VAD, TTS, Hermes, Privacidade) |
| **GPU/CUDA** | 1 device detectado |
| **Áudio** | 11 microfones, 14 saídas |
| **Voice catalog** | Índice do Piper parseado com sucesso (8 vozes pt-BR) |
| **Download de vozes** | Piper (60 MB) + Kokoro (327 MB) baixados, MD5 verificado |
| **Piper binary** | Sintetizou sem erro a 22050 Hz |
| **DSP** | Preset 'room' aplicado, sem erro |
| **Hermes endpoint** | `--doctor --probe` → HTTP 200 |
| **LLM pipeline** | DeepSeek respondeu em português seguindo a persona |
| **Latência** | 1670ms até primeiro áudio (LLM + TTS) |
| **Pipeline completo** | `--text` com LLM + Piper binary TTS + DSP → funcional |

### Gaps encontrados

| Gap | Detalhe | Workaround |
|---|---|---|
| **Kokoro + espeak-ng no Windows** | `language "p" is not supported by the espeak backend` — espeak-ng não tem dados de pt-BR no Windows | `TTS_BACKEND=piper-binary` |
| **`auto` backend no Windows** | Tenta Kokoro primeiro (falha no espeak-ng), cai para piper-python (não instalado em Windows), não alcança piper-binary | `TTS_BACKEND=piper-binary` explícito |
| **Microfone aberto** | Não testado (SSH remoto, sem interação) | Aguarda teste local |
| **Wake word real** | openWakeWord instalado mas não testado com áudio real | Aguarda teste local |

### O que NÃO foi testado (ainda)

- Microfone aberto com wake word (`hermes-voice` sem `--text`)
- Barge-in / supressão de eco com hardware real
- Endpointing adaptativo com áudio real
- Modo `ptt` (hook de teclado + EDR)
- macOS (não disponível)
- Piper Python backend (não instalável em Windows)

---

## Onde eu apostaria que está o problema

Em ordem de probabilidade.

**1. Latência da sondagem de endpoint bloqueia o loop de áudio.**
A sondagem chama `stt.transcribe()` de forma síncrona na thread que consome
frames. Em GPU são ~150 ms, aceitável. Em CPU podem ser 1–3 s, e a fila do
`FrameSource` tem 64 frames (~2 s) e descarta os antigos quando enche. Ou seja:
**em CPU, a sondagem provavelmente engole áudio.** A correção é rodar a sondagem
numa thread, ou desligar `ADAPTIVE_ENDPOINT` quando `WHISPER_DEVICE=cpu`. Não
implementei porque não posso medir.

**2. Divergência de esquema no `voices.json`.** Ver acima.

**3. Assinatura da API do Kokoro.** Se `create()` tiver outra ordem de parâmetros
ou devolver outro formato, o backend quebra no primeiro uso.

**4. Sample rate do Piper.** O código lê `audio.sample_rate` do `.onnx.json`, com
fallback para 22050. Se um `.json` não tiver esse campo, a voz sai com pitch
errado em vez de falhar — pior que erro, porque parece funcionar.

**5. Alinhamento da supressão de eco no hardware real.** O teste usa eco
sintético com atraso constante. Driver real tem jitter, e o buffer do
`RawOutputStream` introduz atraso que não modelei. Pode ser que precise de janela
de busca maior que 320 ms.

**6. Números de latência do README são estimativa.** Vêm de benchmarks
publicados dos componentes, não de medição nesta base de código. `--verbose`
existe para você medir; substitua os números pelos seus.

---

## Roteiro de verificação manual

Na primeira vez que rodar em hardware real, nesta ordem:

```bash
hermes-voice --doctor                       # 1. ambiente
hermes-voice voices --languages             # 2. o índice do Piper carregou?
hermes-voice voices --install pt_BR-faber-medium   # 3. download e MD5
hermes-voice --text --no-tts                # 4. só o Hermes
hermes-voice --text                         # 5. + síntese
hermes-voice --devices                      # 6. dispositivos
hermes-voice --trigger console --no-tts     # 7. só o STT
hermes-voice --trigger console              # 8. pipeline, gatilho manual
hermes-voice --verbose                      # 9. microfone aberto, com tempos
```

Anote o que falhar. Os passos 2, 3 e 9 são os que exercitam código nunca
executado.

Para o DSP, compare de ouvido:

```bash
hermes-voice --text --dsp off
hermes-voice --text --dsp room
hermes-voice --text --dsp intercom
```

---

## O que este documento não é

Não é lista de bugs conhecidos — bug conhecido é corrigido, não documentado. É a
fronteira entre o que foi verificado e o que foi apenas escrito com cuidado.

Se você encontrar algo desta lista funcionando, remova a linha. Se encontrar
falhando, abra issue e mova para o `CHANGELOG.md` quando corrigir.
