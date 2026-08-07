# Voz, direitos e o que este projeto suporta

Este documento existe porque a pergunta aparece sempre: *"posso usar a voz de
[personagem / ator / dublador]?"* A resposta curta é que depende de quem é o dono
da voz, e quase nunca é você. A resposta longa está abaixo, com os caminhos que
funcionam.

Não é parecer jurídico. É um resumo do terreno para você conversar com quem
possa dar um, se for o caso.

---

## O que vem pronto

Cinco vozes pt-BR, todas gratuitas, todas com licença que permite uso comercial:

```bash
hermes-voice voices                          # lista e mostra o que está instalado
hermes-voice voices --install pm_alex        # baixa
hermes-voice --voice pm_alex                 # usa
```

| Voz | Engine | Licença dos pesos | Comercial |
|---|---|---|---|
| `pt_BR-faber-medium` | Piper | MIT | sim |
| `pt_BR-edresson-low` | Piper | MIT | sim |
| `pm_alex` | Kokoro-82M | Apache-2.0 | sim |
| `pm_santa` | Kokoro-82M | Apache-2.0 | sim |
| `pf_dora` | Kokoro-82M | Apache-2.0 | sim |

Nenhuma exige conta, chave de API ou aceitar termos de uso. Nenhuma delas imita
uma pessoa real identificável.

**Kokoro não faz clonagem** — são vozes fixas de preset. Piper também não. Essa
é uma escolha deste projeto, não uma limitação acidental.

---

## Se você quer um timbre diferente

Em ordem de esforço, e todas as três são limpas:

### 1. Ajuste o processamento, não a voz

Provavelmente o caminho mais subestimado. Boa parte do que as pessoas
identificam como "a voz do assistente de ficção científica" não está no timbre —
está no processamento. Voz masculina grátis mais `--dsp intercom` chega
surpreendentemente perto, e custa zero.

```bash
hermes-voice --voice pm_alex --dsp intercom
```

Experimente os cinco presets antes de concluir que precisa de outra voz.

### 2. Grave a sua própria voz

Você é o titular dos direitos sobre a sua voz. Um backend de síntese por
referência (ver adiante) sintetiza a partir de uma amostra curta sua. Isso é
legítimo, comum, e o resultado é seu.

### 3. Contrate ou licencie

Dublagem e locução são profissões. Locutores fazem sessões comerciais, e há um
mercado crescente de licenciamento de voz para uso em IA — em parte, justamente
porque a clonagem não autorizada se tornou um problema para a categoria.

Se você quer poucas frases de sistema, é sessão curta de estúdio, não licença
perpétua de voz sintética. Agências de locução têm bancos de vozes com
licenciamento pronto. O resultado é exclusivo, documentado e você pode mostrar
para qualquer pessoa.

---

## O terreno jurídico

Quatro camadas independentes. Uma autorização em uma não cobre as outras.

### Direitos de personalidade

No Brasil, o art. 20 do Código Civil trata do uso não autorizado da imagem e de
atributos da pessoa. A voz é reconhecida como atributo de personalidade, e a
proteção não depende de registro nem de a pessoa ser famosa. O art. 21 protege a
vida privada.

Nos Estados Unidos existe o *right of publicity*, que varia por estado; há
precedentes específicos sobre imitação vocal em publicidade. Na União Europeia a
proteção vem por direitos da personalidade nacionais somada ao GDPR.

### Direito conexo do intérprete

Um dublador ou locutor tem direito sobre a **interpretação**, separado do direito
sobre o roteiro ou a obra. No Brasil isso está na Lei 9.610/98. Licenciar a obra
não licencia a performance, e vice-versa.

Consequência prática: mesmo que uma gravação esteja disponível publicamente, o
intérprete mantém direitos sobre ela.

### Voz como dado biométrico

Sob a LGPD, dado biométrico é dado pessoal sensível. Voz identifica uma pessoa, e
uma amostra de referência para clonagem é tratamento de dado sensível — o que
exige base legal, normalmente consentimento específico e destacado. O GDPR trata
de forma equivalente quando a voz é usada para identificar unicamente alguém.

Isso vale inclusive para uso doméstico em alguns entendimentos, e certamente para
qualquer coisa que saia da sua máquina.

### Marca

Nome de personagem e nome de produto podem ser marca registrada, o que é
independente de tudo acima. Marca protege a identificação de origem: o problema é
sugerir afiliação ou endosso que não existe. Titulares de marca famosa costumam
defendê-la ativamente na categoria em que atuam, e há casos conhecidos de
produtos de IA que precisaram ser renomeados por isso.

Se você for renomear um fork deste projeto, vale pesquisar a marca antes de
construir audiência. Renomear depois custa estrelas, links e SEO. Escolher bem
antes custa nada.

---

## O que este projeto suporta, e o que não

**Suporta:** as cinco vozes do catálogo; ajuste de prosódia e DSP; síntese a
partir de referência para voz própria ou voz que você tenha direito de usar.

**Não suporta, e não será aceito em contribuição:** instruções, ferramentas ou
funcionalidades voltadas a reproduzir a voz de uma pessoa real identificável sem
autorização dela. Vale para dubladores, locutores, figuras públicas e pessoas
conhecidas suas, e vale igualmente para uso doméstico.

O motivo é simples: um aviso de responsabilidade transfere risco entre quem
publica e quem usa, e não faz nada pela pessoa cuja voz está em jogo — que é a
parte afetada e não participa de nenhum acordo.

Se você decidir seguir outro caminho num fork seu, a decisão e a responsabilidade
são suas. Este documento existe para que ela seja informada.

---

## Nota sobre XTTS-v2

O XTTS-v2 é a opção open source mais conhecida para síntese por referência, e
faz sentido considerá-lo. Dois pontos antes:

**Licença dos pesos.** O modelo é distribuído sob a Coqui Public Model License,
que **restringe uso comercial**. Isso não é coberto pela licença Apache-2.0 deste
projeto. Se você embarcar XTTS num produto comercial assumindo que a licença do
repositório cobre tudo, a suposição está errada. É por isso que ele não está no
caminho padrão.

**Peso.** Exige PyTorch, na ordem de 2,5 GB, contra 63 MB do Piper e 327 MB do
Kokoro. Vai contra o objetivo de funcionar de imediato.

A Coqui, empresa original, encerrou as operações; o desenvolvimento segue em fork
comunitário. Se você quiser usar de todo modo:

```bash
pip install "hermes-voice[xtts]"
hermes-voice --tts xtts --reference minha_voz.wav
```

O backend imprime a restrição de licença ao carregar, no terminal — não só aqui
na documentação. Use com a sua própria voz.

---

## Resumo

| Você quer | Faça |
|---|---|
| Só funcionar | Nada. `pt_BR-faber-medium` vem pronto. |
| Melhor qualidade grátis | `hermes-voice voices --install pm_alex` |
| Caráter, presença de sala | `--dsp room` ou `--dsp intercom` |
| A sua própria voz | Extra `xtts`, com a ressalva de licença |
| Um timbre específico de alguém | Contrate ou licencie. É a única via limpa. |
