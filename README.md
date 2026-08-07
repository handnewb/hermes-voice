# hermes-voice

**Voice-enabled personal assistant for [Hermes Agent](https://github.com/NousResearch/hermes-agent).** Open mic with wake word, fully local — no API keys, no accounts, 35 languages.

[![CI](https://github.com/handnewb/hermes-voice/actions/workflows/ci.yml/badge.svg)](https://github.com/handnewb/hermes-voice/actions/workflows/ci.yml)
[![CodeQL](https://github.com/handnewb/hermes-voice/actions/workflows/codeql.yml/badge.svg)](https://github.com/handnewb/hermes-voice/actions/workflows/codeql.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

```
você:    "Jarvis, o que rodou essa noite?"
hermes:  "Cento e quarenta e sete mil eventos, senhor. Três escalados."
você:    "detalha o terceiro"          ← sem repetir a palavra de ativação
hermes:  "Conexão para domínio registrado há dezoito horas. Isolei."
         ...20 segundos de silêncio...
                                        ← volta a dormir sozinho
```

<details>
<summary><b>English</b> — the documentation below is in Brazilian Portuguese. Short version here.</summary>

Talk to your Hermes agent the way you would talk to a person. Say the wake word
and speak; the wake word opens a **session**, so follow-up turns need no
repetition. The session closes on its own when you stop talking.

```bash
pip install "hermes-voice[wake,kokoro]"
hermes-voice voices --install pt_BR-faber-medium   # or --lang en, es, fr, zh...
hermes-voice --doctor
hermes-voice
```

**Runs entirely offline.** Speech recognition (faster-whisper), voice activity
detection (Silero), wake word (openWakeWord) and synthesis (Piper, Kokoro-82M) all
run locally. The only address contacted at runtime is your own Hermes endpoint.

- **Adaptive turn-taking** — instead of a fixed silence threshold, it transcribes
  early and checks whether the sentence *looks finished*. "I want" waits;
  "what's the status?" answers immediately.
- **Barge-in without external dependencies** — echo suppression in ~200 lines of
  numpy. Zero false positives across four delays and four room gains.
- **Presence DSP** — high-pass, compression, presence lift, short room reverb.
  Much of what people recognise as "assistant voice" is processing, not timbre.
- **Voices in 35 languages** via the public Piper index, MD5-verified, plus 9 via
  Kokoro. All default voices permit commercial use.
- **Voice cloning of real people is deliberately unsupported.** Reasoning and
  clean alternatives in [`docs/VOICE_LICENSING.md`](docs/VOICE_LICENSING.md).

Read [`docs/VERIFICATION.md`](docs/VERIFICATION.md) before trusting it: it states
plainly which parts have run on real hardware and which have not.

Documentation and the default persona are Brazilian Portuguese; the architecture
and voice catalog are language-agnostic. Contributions welcome, including
translations — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

</details>

> **Estado de verificação.** Os componentes têm 229 testes automatizados, mas
> partes do projeto — todo o I/O de áudio, as engines de voz e os downloads —
> nunca foram executadas em hardware real. Antes de confiar, leia
> [`docs/VERIFICATION.md`](docs/VERIFICATION.md): ele lista o que foi verificado,
> o que não foi, e onde eu apostaria que há problema.

---

## O ponto de design

Se você tem que dizer a palavra de ativação a cada turno, isso é **controle remoto**, não conversa. Aqui a palavra abre uma **sessão**, e dentro dela você fala normalmente.

```
DORMANT ──"Jarvis"──────────► LISTENING
LISTENING ──silêncio 700ms───► THINKING ──1º áudio──► SPEAKING
SPEAKING ──fim do áudio──────► FOLLOW_UP
FOLLOW_UP ──você fala────────► LISTENING     (sem repetir a palavra)
FOLLOW_UP ──20s parado───────► DORMANT
```

Os dois parâmetros que definem a sensação:

| Variável | Padrão | Efeito |
|---|---|---|
| `SILENCE_MS` | `700` | Silêncio que encerra sua fala. Abaixo de 400 corta você em pausa natural; acima de 900 soa hesitante. |
| `FOLLOW_UP_SECONDS` | `20` | Quanto a sessão fica aberta depois da resposta. |

Ajuste de ouvido, não de intuição.

## Começando

```bash
pip install "hermes-voice[wake,kokoro]"
hermes-voice voices --install all   # baixa vozes e modelos, ~400 MB, uma vez
hermes-voice --doctor               # diz exatamente o que falta
hermes-voice                        # fale
```

**Nenhuma conta, nenhuma chave de API, nenhum serviço de nuvem.** Todas as
engines rodam localmente. O único endereço que o programa contata em execução é
o seu próprio Hermes.

Ou a partir do repositório, com o setup que baixa a voz e o binário do Piper:

```powershell
git clone https://github.com/handnewb/hermes-voice && cd hermes-voice
.\scripts\setup.ps1            # Windows
./scripts/setup.sh             # Linux e macOS
```

**Comece sempre pelo `--doctor`.** Num projeto de voz, 90% dos problemas são de ambiente: driver de áudio, cuDNN faltando, wheel que não compilou, chave ausente, EDR bloqueando. O doctor verifica os oito grupos e diz a correção de cada falha, em vez de você descobrir na prática.

## Três modos de gatilho

| Modo | Como | Quando usar |
|---|---|---|
| `--trigger wake` *(padrão)* | Diga a palavra e fale | Uso normal |
| `--trigger console` | ENTER inicia, ENTER envia | Quando não pode ter microfone aberto nem hook de teclado |
| `--trigger ptt` | Segure uma tecla | Ambiente ruidoso |

O modo `console` existe por um motivo específico. Um hook global de teclado (`SetWindowsHookEx`, usado pelo `pynput` no modo `ptt`) é a assinatura clássica de keylogger; somado a captura de microfone e egress de rede, forma a tríade comportamental de um implante de spyware. Motor de EDR comportamental vai sinalizar, e vai estar certo. O modo `console` não instala hook nenhum. Ver [SECURITY.md](SECURITY.md).

## A palavra de ativação

Três modos, com tradeoff explícito. Nenhum exige conta.

| `WAKE_BACKEND` | Palavra | Precisão | Custo |
|---|---|---|---|
| `auto` *(padrão)* | Catálogo do openWakeWord | Melhor | Exige "**ei** jarvis"; só 4 palavras |
| `keyword` | **Qualquer palavra, qualquer idioma** | Menor | Transcreve a fala antes de ativar |
| `open` | Nenhuma — qualquer fala | — | Transcreve tudo. Só com fone. |

O modo `auto` usa modelos pré-treinados (`hey_jarvis`, `alexa`, `hey_mycroft`,
`hey_rhasspy`). Melhor detecção, mas catálogo pequeno e você precisa dizer "ei"
antes.

O modo `keyword` aceita a palavra que você quiser, em qualquer idioma, sem treinar
nada: quando o VAD detecta fala, um Whisper `tiny` transcreve a janela e procura a
palavra com tolerância a erro de transcrição.

```bash
# .env
WAKE_BACKEND=keyword
WAKE_WORDS=jarvis,jarvez,gervis
```

A lista separada por vírgula é o mecanismo que importa. A tolerância de edição é
limitada a 1 de propósito — com 2, "computador" passa a aceitar "compilador", e
ativação falsa é pior que ativação perdida. Para recuperar o que o Whisper erra na
*sua* voz, **adicione apelidos** em vez de afrouxar o limiar: lista exata não
introduz colisão nova.

Escolha palavra distintiva de três sílabas ou mais, e verifique colisão antes de
adotar: "hermes" colide com "herpes" a uma edição, "sofia" com "sofa". Isso vale
para qualquer sistema de wake word.

**Custo de privacidade do modo `keyword`**, e é real: a fala é transcrita antes de
haver ativação. Não é transcrição contínua — só roda quando o VAD vê fala, nada é
gravado e nada sai da máquina — mas a garantia "em `DORMANT` nada é transcrito"
não vale nesse modo. Por isso não é o padrão, e o `--doctor` avisa.

Para palavra própria com a precisão do modelo treinado, o openWakeWord tem um
pipeline de treinamento com dados sintéticos. Ver [roadmap](docs/ROADMAP.md).

## Voz

Centenas de vozes em dezenas de idiomas, todas gratuitas, todas com licença que
permite uso comercial. Duas engines, ambas locais.

```bash
hermes-voice voices --languages           # que idiomas existem
hermes-voice voices --lang es             # filtra
hermes-voice voices --install em_alex
hermes-voice --voice em_alex
```

**Piper**: o catálogo não está fixado no código. O programa consulta o
`voices.json` publicado no Hugging Face em tempo de execução — 35 idiomas,
centenas de vozes, licença MIT — e verifica o MD5 que vem no próprio índice. Voz
nova no upstream aparece sem release nosso. Se o índice estiver inacessível, o
Kokoro continua funcionando e um aviso é registrado.

**Kokoro-82M**: 54 vozes em 9 idiomas num único arquivo de pesos Apache-2.0 —
inglês americano e britânico, espanhol, francês, hindi, italiano, japonês,
português do Brasil e mandarim.

| Voz | Engine | Licença | Nota |
|---|---|---|---|
| `pt_BR-faber-medium` | Piper | MIT | **Padrão.** 63 MB, roda em CPU, ~50 ms. |
| `pm_alex` | Kokoro | Apache-2.0 | pt-BR, prosódia bem melhor que Piper. |
| `am_michael` | Kokoro | Apache-2.0 | en-US masculina. |
| `em_alex` | Kokoro | Apache-2.0 | Espanhol masculina. |
| `zm_yunxi` | Kokoro | Apache-2.0 | Mandarim masculina. |
| ...e centenas de vozes Piper | Piper | MIT | `voices --lang <código>` |

Kokoro roda via `kokoro-onnx` e não pelo pacote oficial, porque o oficial arrasta
PyTorch (~2,5 GB) e este projeto já tem onnxruntime instalado para o VAD.

Nenhuma das duas engines faz clonagem de voz — são vozes fixas. Isso é escolha do
projeto, e [`docs/VOICE_LICENSING.md`](docs/VOICE_LICENSING.md) explica o terreno
jurídico (direitos de personalidade, direito conexo do intérprete, voz como dado
biométrico) e os caminhos limpos para quem quer um timbre específico.

### Escolhendo a voz de forma séria

[`docs/script_avaliacao_voz.md`](docs/script_avaliacao_voz.md) tem um script de 11
blocos, cada um isolando um modo de falha, com três critérios eliminatórios.

Os dois blocos que ninguém pensa em testar: a voz precisa conseguir **dizer não**
e **admitir ignorância** sem soar agressiva nem submissa. Vozes de pt-BR são quase
todas treinadas para atendimento, vêm com sorriso embutido, e falham feio
justamente nessas duas — que são as falas que mais importam num assistente que
confirma ação destrutiva.

Para estabilidade long-form há
[`docs/monologo_1000_palavras.txt`](docs/monologo_1000_palavras.txt): 1.031
palavras corridas, ~7 minutos. Compare o último minuto com o primeiro.

## O estágio que faz mais diferença que o timbre

```bash
hermes-voice --dsp room
```

Boa parte do que as pessoas identificam como "voz de assistente de ficção científica" não está no timbre — está no **processamento**. A fala é tratada como se viesse de alto-falantes num ambiente, e nenhum TTS entrega isso de fábrica.

Quatro estágios, em streaming, só com numpy:

1. **High-pass** em 110 Hz — remove o peso "boca no microfone" que denuncia locução de proximidade
2. **Compressor** — achata a dinâmica; voz calma tem pouca variação de volume, e é o que dá sensação de controle
3. **Realce de presença** em 3 kHz — inteligibilidade a distância
4. **Reverb curto de sala**, muito baixo — dá lugar ao som

Cinco presets: `off`, `room`, `close`, `hall`, `intercom`. Comece em `room`. Use `hall` uma vez só para ouvir o que cada parâmetro faz — ele exagera de propósito.

Exagerar no reverb é o erro mais comum e soa como banheiro.

## Fluidez

Três coisas separam "conversa" de "controle remoto por voz", e nenhuma delas é o
timbre.

**Endpointing adaptativo.** Limiar fixo de silêncio não funciona: 400 ms corta
você no meio de uma pausa de pensamento, 1000 ms deixa o assistente hesitante. A
duração da pausa carrega significado. Então em vez de contar silêncio, o sistema
transcreve num limiar curto e olha se a frase *parece terminada*:

```
"eu quero"                    → pendurado, espera até 1250 ms
"o status do"                 → preposição solta, espera
"qual o status?"              → pergunta fechada, responde em 380 ms
"isola a máquina agora"       → imperativo completo, responde
```

Se o texto não cresceu entre duas sondagens, encerra de todo modo — pessoa
distraída no meio da frase não pode travar o turno.

**Normalização de texto.** Nenhum TTS local lê `R$ 1.500,00` ou `08/06/2026`
corretamente. Piper soletra dígito por dígito. A normalização converte antes de
sintetizar, e o ganho de qualidade percebida é maior que trocar de engine:

```
"R$ 1.500,50 em 08/06/2026 às 14:30, 99,7% de disponibilidade"
→ "mil e quinhentos reais e cinquenta centavos em oito de junho de dois mil e
   vinte e seis às quatorze e meia, noventa e nove vírgula sete por cento..."
```

**Interrupção de verdade.** Ver a seção de duplex abaixo.

Ressalva de idioma: o endpointing e a normalização são **específicos de pt-BR**.
A arquitetura é multilíngue e o STT, o VAD e as vozes também, mas as listas de
palavras em `endpoint.py`, as regras de `normalize.py` e a persona são de
português. Outros idiomas funcionam com limiar fixo e sem normalização — pior,
não quebrado. Adicionar um idioma são quatro pontos, listados em
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Latência

O ganho não vem de otimizar cada estágio, vem de **pipelinar**: a primeira frase da resposta vai para o TTS enquanto o modelo ainda gera a segunda.

| Estágio | Alvo |
|---|---|
| Fim de fala (Silero VAD) | ~700 ms (é o `SILENCE_MS`, ajustável) |
| STT (`large-v3-turbo`, GPU) | 200–400 ms |
| Hermes até o 1º token | 100–500 ms |
| TTS até o 1º áudio | 150–300 ms |
| **Percebido** | **~700–1000 ms** |

`--verbose` imprime o tempo real de cada estágio por turno. Meça antes de otimizar: quando parece lento, o culpado costuma ser o tempo até o primeiro token do Hermes, não o STT nem o TTS — que é onde a intuição manda olhar.

## Privacidade

Microfone aberto numa máquina pessoal merece garantia, não configuração. Três propriedades implementadas em [`session.py`](src/hermes_voice/session.py) **por construção** — não é possível desligá-las por engano:

- **Em `DORMANT` nada é transcrito.** Os frames alimentam apenas o detector de palavra de ativação, que roda local e não produz texto.
- **O pré-roll é um `deque` com `maxlen` fixo** de 480 ms. Há teste que alimenta 64 segundos de áudio contínuo e verifica que só 480 ms permanecem.
- **Ao adormecer o buffer é descartado**, explicitamente e inclusive quando já estava dormindo.

Nada toca o disco a menos que você ligue `LOG_TRANSCRIPTS=1`, que é `0` por padrão e aparece como aviso no `--doctor`.

Os 480 ms de pré-roll existem porque o detector dispara ~300 ms depois de a palavra terminar; sem eles você perde a primeira sílaba do que veio em seguida.

Nada de áudio nem de texto sai para provedor de voz, porque não há provedor de voz: Piper, Kokoro, Silero e openWakeWord rodam todos localmente. O único endereço contatado em execução é o seu próprio endpoint do Hermes.

## Duplex e interrupção

`HALF_DUPLEX=1` (padrão): enquanto o assistente fala, o microfone não é avaliado.
Robusto, e o custo é não poder interromper por voz.

`HALF_DUPLEX=0` liga a **supressão de eco** e você pode interromper falando.

Isso não é AEC. AEC de verdade estima a resposta impulsiva da sala com filtro
adaptativo e subtrai o eco do sinal. O que fazemos é mais modesto e resolve o
caso que importa: como nós geramos o áudio de saída, sabemos exatamente o que foi
enviado. Para cada frame do microfone, verificamos se **algum** alinhamento da
referência, dentro de uma janela de 320 ms, explica a energia capturada. Se
explica, é eco. Se não, é você. Duzentas linhas de numpy, zero dependência.

Testado com atraso de 20 a 300 ms e ganho de sala de 0,25 a 1,3: zero falsos
positivos com eco puro, e dispara quando há fala sobreposta.

Consequência prática: você interrompe falando mais alto que a caixa. Não conversa
sobreposto em volume baixo. Com fone nada disso é necessário — não há eco.

## Arquitetura

| Módulo | Responsabilidade |
|---|---|
| `session.py` | Máquina de estados, limites de buffer, limpeza da palavra de ativação |
| `wake.py` | openWakeWord, com adaptador de tamanho de frame |
| `vad.py` | Silero via onnxruntime (sem torch), fallback por energia, histerese |
| `stt.py` | faster-whisper com vocabulário de domínio e queda para CPU |
| `llm.py` | Cliente SSE e o fatiador de sentenças |
| `tts/` | Quatro backends, DSP e playback interrompível |
| `endpoint.py` | Endpointing adaptativo por sintaxe |
| `normalize.py` | Números, datas, siglas e abreviações em pt-BR |
| `echo.py` | Supressão de eco por referência, só numpy |
| `voices.py` | Catálogo e download de vozes e modelos |
| `doctor.py` | Autodiagnóstico |
| `loops.py` | Os três modos de gatilho |

Não existe speech-to-speech local decente em pt-BR hoje — Moshi é inglês e francês, GLM-4-Voice é chinês e inglês, Qwen-Omni sintetiza só inglês e mandarim. Pipeline encadeado é a escolha certa, não um compromisso. Reavaliar em alguns meses.

## Testes

```bash
pip install -e ".[dev]" && pytest
```

229 testes, nenhum exigindo placa de som, GPU, rede ou chave de API. Isso é requisito, não coincidência: projeto de áudio que só pode ser testado com hardware termina sem testes. Os imports de `sounddevice` são preguiçosos de propósito.

O teste que mais vale: o fatiador de sentenças é verificado com deltas de 1 a 23 caracteres, exigindo resultado idêntico. Sem essa propriedade, o áudio muda conforme a velocidade da rede — que foi exatamente o bug que cortava "12:30" ao meio.

## Nome e marcas

O projeto se chama **hermes-voice** e não é afiliado, patrocinado nem endossado por nenhum detentor de marca.

`hey_jarvis` aparece como valor padrão de `WAKE_MODEL` porque é o identificador de um dos poucos modelos pré-treinados que o openWakeWord distribui — é dependência funcional e nome de arquivo de terceiro, não branding deste projeto. Troque em `WAKE_MODEL` para qualquer outro do catálogo (`alexa`, `hey_mycroft`, `hey_rhasspy`), ou treine o seu.

O **nome da persona** é configurável em `docs/persona.md`: o que você chama o seu assistente na sua máquina é decisão sua.

Se você for renomear um fork, pesquise a marca antes de construir audiência. Há [casos conhecidos](docs/VOICE_LICENSING.md) de produtos de IA que precisaram ser renomeados, e renomear depois custa estrelas, links e SEO.

## Contribuindo

[`CONTRIBUTING.md`](CONTRIBUTING.md) para o ambiente e as regras de código.
[`GOVERNANCE.md`](GOVERNANCE.md) para como decisões são tomadas, quem pode o quê,
e qual processo entra em cada estágio do projeto. [`SUPPORT.md`](SUPPORT.md) para
onde perguntar o quê.

Contribuir não exige nenhuma permissão: fork mais pull request cobre todos os
casos. O único gate obrigatório é CI verde.

## Licença

[Apache 2.0](LICENSE) para o código. Modelos e vozes baixados têm licenças
próprias, todas permissivas: Piper e as vozes do rhasspy são MIT, Kokoro-82M é
Apache-2.0, Silero VAD é MIT, openWakeWord é Apache-2.0.

Nenhum componente do caminho padrão restringe uso comercial. Ver
[`docs/VOICE_LICENSING.md`](docs/VOICE_LICENSING.md) para o que fica de fora e
por quê.

## Agradecimentos

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) • [faster-whisper](https://github.com/SYSTRAN/faster-whisper) • [Silero VAD](https://github.com/snakers4/silero-vad) • [Piper](https://github.com/rhasspy/piper) • [openWakeWord](https://github.com/dscripka/openWakeWord) • [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) • [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)
