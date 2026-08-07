# Roadmap

Estado atual: **v1.0.0**. Wake word, VAD, sessão contínua, quatro backends de TTS
e o estágio de DSP estão prontos. O que falta está abaixo, com estimativa honesta
de esforço.

---

## ~~v1 — Wake word e fim de fala~~ — feito em 1.0.0

Substitui a tecla por escuta contínua. Duas peças:

**Silero VAD** (`snakers4/silero-vad`) — ONNX de ~2 MB, inferência em ~1 ms por
janela de 30 ms. Substitui o release da tecla por detecção real de fim de fala.
O parâmetro que importa é o silêncio mínimo: 300 ms parece agressivo mas é o que
faz a conversa fluir; acima de 600 ms o assistente soa hesitante. Faça isso
configurável e ajuste com o ouvido, não com a intuição.

**openWakeWord** — treine "Hermes" como palavra custom. Alternativa: Porcupine
(Picovoice), melhor taxa de falso positivo, gratuito para uso pessoal.

Onde encaixa: `audio_in.Recorder` já mantém o `InputStream` aberto durante toda a
sessão exatamente por isso. Troque o gatilho por wake word e o `stop()` por VAD;
o resto do pipeline não muda.

**Bônus inesperado:** wake word elimina o hook global de teclado, que é hoje o
componente de maior atrito com EDR comportamental. Você troca uma assinatura de
keylogger por microfone sempre ativo. Do ponto de vista do EDR é uma melhora
clara; do ponto de vista de privacidade doméstica, o oposto. Decida com os dois
lados na mesa, não só o primeiro.

**Consequência que não é técnica.** Wake word significa microfone sempre ativo
numa máquina de trabalho, com a família por perto. Antes de ligar: defina que o
ring buffer é circular e limitado (2-3 s bastam para não perder o início da
frase), que ele nunca toca disco, e que a transcrição não vai para log
persistente. Isto é T3 na skill por esse motivo.

## AEC — esforço alto, o item mais pedido

Só necessário se você quiser falar com as caixas abertas. Com fone, pule.

O problema: o microfone escuta a saída, o VAD dispara com a voz do próprio
Hermes, e você entra em loop. Precisa de duas coisas:

1. **Sinal de referência** — captura loopback WASAPI da saída. No Windows,
   `sounddevice` com `WasapiSettings(loopback=True)`, ou `soundcard` que expõe
   isso de forma mais direta.
2. **AEC** — `speexdsp` (`speexdsp-python`) ou o AEC do WebRTC via
   `webrtc-audio-processing`. O WebRTC é melhor mas o binding em Python é
   irregular.

Estimativa honesta: esta é a parte do projeto que vai consumir mais tempo, por
uma margem grande. Alinhamento temporal entre o sinal de referência e o
microfone é onde tudo dá errado — um offset de 20 ms degrada o cancelamento a
ponto de ser inútil, e o offset varia com o driver.

**Atalho pragmático:** meio-caminho que resolve 80% dos casos sem AEC. Enquanto
o TTS está falando, suba o limiar do VAD e exija que a energia detectada supere
a energia conhecida da saída por uma margem. Barato, funciona quando você fala
mais alto que a caixa, e são ~30 linhas. Faça isto antes de tentar AEC de verdade.

## Piper persistente — esforço baixo, ganho de ~150 ms

Hoje `PiperBinary.synth` gera um processo por frase: ~150 ms de startup em cada
uma. Some isso ao longo de uma resposta de quatro frases e você perde meio
segundo.

Solução: processo de longa duração alimentado por stdin. O obstáculo é que o
`--output_raw` não delimita utterances no stdout, então você não sabe onde uma
termina. Duas saídas: `--output-dir` com arquivos por frase (perde streaming), ou
`--json-input` que retorna metadados por utterance. Vale medir se o ganho de
150 ms justifica — se você migrar para Azure, o problema desaparece.

## Ferramentas — esforço médio

O ponto onde isto deixa de ser um brinquedo. O Hermes já orquestra a frota do
SOC; a voz passa a ser interface para consultar estado e disparar playbooks.

Duas regras que não devem ceder:

**Confirmação por voz para ação destrutiva, sempre.** Reconhecimento de fala
erra, e um falso positivo que fecha ticket ou isola endpoint é caro. O
`persona_jarvis_ptbr.md` já contém essa regra; ela precisa ser reforçada na
camada de ferramenta, não confiada ao prompt.

**Nada de leitura de segredo em voz alta.** Vale a mesma proibição permanente
que se aplica a qualquer cofre de segredos. Áudio é o pior canal possível para
credencial: fica no ar da sala, não tem controle de acesso, e você não sabe quem
está ouvindo.

## Não faça

**Speech-to-speech local em pt-BR.** Ainda não existe de forma decente. Moshi é
inglês/francês, GLM-4-Voice é chinês/inglês, Qwen-Omni sintetiza só inglês e
mandarim. Reavalie em uns seis meses; o campo se move rápido.

**Clonagem de voz de pessoa real.** Coberto no `SKILL.md` como restrição T3.

**Otimizar antes de medir.** `--verbose` existe para isso. Quando a resposta
parece lenta, o culpado costuma ser o tempo até o primeiro token do Hermes — não
o STT nem o TTS, que é onde a intuição manda olhar.

## Idiomas além do pt-BR — esforço baixo, ajuda bem-vinda

A arquitetura não é específica de português. O que é: o arquivo de persona, o
`DEFAULT_HINT` do Whisper, o regex de limpeza da palavra de ativação em
`session.py`, e as abreviações do fatiador de sentenças (`Dr.`, `Sr.`, `etc.`).

Para adicionar um idioma, esses quatro pontos são o trabalho inteiro. O STT
(Whisper) e o VAD (Silero) já são multilíngues, e Piper tem vozes para dezenas de
idiomas. Abra uma issue dizendo qual idioma e eu ajudo a mapear os pontos.
