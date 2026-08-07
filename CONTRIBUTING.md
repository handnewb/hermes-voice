# Contribuindo

Contribuição é bem-vinda. Este documento existe para você não perder tempo.

## Preparar o ambiente

```bash
git clone https://github.com/handnewb/hermes-voice
cd hermes-voice
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,all]"
cp .env.example .env
hermes-voice --doctor
```

## Antes de abrir PR

```bash
ruff check . && ruff format . && pytest
```

## A regra que mais importa aqui

**Nenhum teste pode exigir placa de som, GPU, rede ou chave de API.**

Isso não é preferência, é o que mantém a suíte viva. Projetos de áudio que só
podem ser testados com hardware terminam sem testes. Os imports de `sounddevice`
são preguiçosos de propósito (`audio._sd()`) para que o pacote seja importável e
testável num runner sem áudio.

O que dá para testar sem hardware, e está testado: fatiador de sentenças,
máquina de estados, limites de buffer, limpeza da palavra de ativação, cadeia de
DSP (numericamente, com tom sintético), parsing de configuração, redação de
segredos.

O que precisa de teste manual: qualidade de detecção da palavra de ativação,
sensação de latência, timbre. Descreva no PR o que você testou à mão, em qual SO
e com qual backend.

## Padrões de código

- `ruff` cuida de estilo e imports. Não discuta formatação, rode a ferramenta.
- Docstrings e comentários em pt-BR. Nomes de identificadores em inglês.
- Comentário explica **por que**, não o que. Se o código precisa de comentário
  para dizer o que faz, reescreva o código.
- Sem dependência nova sem justificativa no PR. Cada uma é uma decisão de
  cadeia de suprimentos, e este projeto já grava áudio — o orçamento de confiança
  é curto.

## Mudanças que exigem discussão antes do código

Abra issue primeiro se o PR:

- alterar **captura, retenção ou envio de áudio**, incluindo tamanho de buffer,
  o que é transcrito em cada estado, ou o que vai para disco;
- adicionar backend que envie áudio (não texto) para serviço externo;
- mexer nas três garantias descritas em `SECURITY.md`.

Não é burocracia. Essas garantias são a razão pela qual dá para rodar isto numa
máquina com outras pessoas por perto, e mudá-las sem discussão quebra a premissa
do projeto.

## O que não será aceito

**Clonagem de voz de pessoa real a partir de amostra.** Voz é atributo de
personalidade (no Brasil, art. 20 do Código Civil), há direito conexo do
intérprete, e voz é dado biométrico sob LGPD e GDPR. Vale também para dubladores
e para "só uso pessoal".

A alternativa existe e é melhor: Voice Design da ElevenLabs gera timbre inédito a
partir de descrição textual. Nenhuma pessoa real envolvida, e o resultado é seu.
Há um prompt de exemplo no `README.md`.

## Onde ajudar

`docs/ROADMAP.md` tem o backlog com estimativa honesta de esforço. Os itens de
maior impacto hoje:

- **AEC** (cancelamento de eco) para conversar com caixas abertas. É o item mais
  difícil e o mais pedido.
- **Palavra de ativação em pt-BR** treinada nativamente, em vez do modelo inglês.
- **Piper com processo persistente**, para eliminar os ~150 ms de startup.
- **Mais idiomas.** A arquitetura não é específica de português; a persona e o
  vocabulário são.

## Governança e permissões

[`GOVERNANCE.md`](GOVERNANCE.md) descreve como decisões são tomadas, os caminhos
protegidos e o que cada papel do GitHub pode fazer.

Dois pontos que economizam tempo: **contribuir não exige permissão nenhuma** —
fork mais pull request cobre todos os casos, e você não precisa pedir acesso. E o
papel Triage, concedido depois de um ou dois PRs aceitos, é o primeiro passo
normal: permite rotular e fechar issue sem tocar em código.

## Código de conduta

Ver [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
