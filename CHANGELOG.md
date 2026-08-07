# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Alterado — sem dependência de serviço externo

- **Removidos ElevenLabs e Azure Speech.** O projeto passa a ser inteiramente
  local: nenhuma chave de API, nenhum cadastro, nenhum egress em execução além
  do próprio endpoint do Hermes. `Config.SECRET_FIELDS` tem um único item.
- **Porcupine substituído por openWakeWord** (Apache-2.0, sem conta). Custo
  documentado: exige "ei jarvis" em vez de "jarvis", e erra mais.
- **Catálogo de vozes** com cinco opções pt-BR gratuitas e licença que permite
  uso comercial, instaláveis com `hermes-voice voices --install`.

### Adicionado — fluidez

- **Endpointing adaptativo** (`endpoint.py`): em vez de limiar fixo de silêncio,
  transcreve num limiar curto e avalia se a frase parece sintaticamente
  completa. "eu quero" espera; "qual o status?" responde. Se o texto não cresce
  entre sondagens, encerra de todo modo.
- **Normalização pt-BR** (`normalize.py`): números, moeda, datas, horas,
  percentuais, ordinais, abreviações e siglas por extenso antes de sintetizar.
- **Supressão de eco** (`echo.py`): barge-in real com `HALF_DUPLEX=0`, só numpy.
  Verifica se algum alinhamento da referência explica a energia do microfone.
  Zero falsos positivos em atrasos de 20–300 ms e ganhos de sala de 0,25–1,3.
- **Backend Kokoro-82M** via `kokoro-onnx`, pesos Apache-2.0, sem PyTorch.

### Segurança

- `docs/VOICE_LICENSING.md`: direitos de personalidade, direito conexo do
  intérprete, voz como dado biométrico, e os caminhos limpos para um timbre
  específico. Escrito para a pessoa decidir informada.
- XTTS-v2 fora do caminho padrão: pesos non-commercial não cobertos pela licença
  Apache-2.0 do repositório.
- Persona empacotada no wheel, para existir numa instalação por pip sem que o
  projeto escreva dentro de `site-packages`.

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
