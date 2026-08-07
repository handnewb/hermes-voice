# Governança

Como decisões são tomadas, quem pode fazer o quê, e quando cada camada de
processo entra.

## O princípio

**Processo se adiciona quando a dor aparece, não antes.**

Projeto com um mantenedor e zero contribuidores que exige duas aprovações e três
revisores é teatro: o mantenedor aprova a si mesmo, o ritual não pega nada, e o
primeiro contribuidor desiste na terceira rodada de burocracia. Isso é engessar
sem ganhar robustez.

Por outro lado, projeto que grava áudio e baixa modelos precisa de trilho real
onde importa. A solução não é escolher entre robusto e leve — é ser rígido num
conjunto pequeno de caminhos e frouxo no resto.

Este documento é organizado por **estágio**. Cada estágio lista o que vale agora e
o gatilho que abre o próximo. Não pule etapas por antecipação.

---

## Estágio atual: 0 — um mantenedor

O que vale hoje.

**Tudo passa por pull request, inclusive do mantenedor.** Não por cerimônia: é o
que garante que o CI roda sempre e que o histórico fica revisável. Push direto na
`main` está bloqueado.

**Sem exigência de aprovação.** Com uma pessoa, aprovação é auto-aprovação. O que
protege é o CI verde, não a assinatura.

**Merge por squash, sempre.** Um commit por mudança na `main`, mensagem
descritiva, `git bisect` utilizável. Merge commit e rebase estão desligados.

**Gate obrigatório:** `lint` e `build` verdes. Falha em qualquer um bloqueia.

### Gatilho para o estágio 1

Duas pessoas além do mantenedor com pull request aceito, ou a primeira
contribuição que toca caminho protegido.

---

## Estágio 1 — contribuidores recorrentes

Adiciona:

- **Uma aprovação obrigatória**, de alguém que não é o autor.
- **`CODEOWNERS` ativo** nos caminhos protegidos (lista abaixo).
- **Papel Triage** para quem contribui com frequência — não Write.
- **Aprovação manual de CI para primeira contribuição** de conta nova. É a defesa
  contra workflow malicioso vindo de fork.

### Gatilho para o estágio 2

Um segundo mantenedor com direito de merge, ou volume de issues que uma pessoa não
triaga em 48 h.

---

## Estágio 2 — mais de um mantenedor

Adiciona:

- `MAINTAINERS.md` com nomes, áreas e fuso.
- **Duas aprovações** para caminhos protegidos; uma para o resto.
- Rotação de release, para não haver dependência de uma pessoa só.
- Decisão por consenso simples; empate persistente fica com quem mantém há mais
  tempo. Registrada na issue, não em conversa privada.

---

## Papéis no GitHub, e o que cada um pode fazer

Concessão de permissão é irreversível na prática: retirar acesso de alguém é
socialmente caro, então conceda devagar.

| Papel | Pode | Quando conceder |
|---|---|---|
| **Read** (público) | Fork, pull request, issue, discussion | Automático. É o suficiente para contribuir. |
| **Triage** | Rotular, fechar e atribuir issue; sem escrever código | Após 1–2 PRs aceitos. Baixo risco, alívio real. É o papel mais subutilizado do GitHub. |
| **Write** | Push em branch, merge de PR | Após 3+ PRs aceitos, incluindo um em caminho protegido. Só com histórico. |
| **Maintain** | Configurações não sensíveis | Segundo mantenedor de fato. |
| **Admin** | Tudo, inclusive apagar o repositório | Só o dono. |

**Contribuir não exige nenhuma permissão.** Fork mais pull request cobre 100% dos
casos, e é assim que deve ser: quem chega não precisa pedir acesso, precisa abrir
um PR.

---

## Caminhos protegidos

Estes exigem revisão mais atenta, e no estágio 1 entram no `CODEOWNERS`. Não é
sobre confiança na pessoa — é sobre o que a mudança pode causar.

| Caminho | Por quê |
|---|---|
| `src/hermes_voice/session.py` | Contém as três garantias de privacidade. Mudança aqui pode fazer o projeto transcrever o que não devia, sem que nada pareça errado. |
| `src/hermes_voice/audio.py` | Captura de microfone e limites de buffer. |
| `src/hermes_voice/echo.py` | Buffer de referência do áudio de saída. |
| `.github/workflows/**` | **Vetor de ataque clássico.** Um workflow alterado pode exfiltrar segredo, publicar release falso ou injetar código no artefato. Trate como o arquivo mais sensível do repositório. |
| `pyproject.toml` | Dependência nova é decisão de cadeia de suprimentos. |
| `docs/persona.md`, `src/hermes_voice/data/persona.md` | Define o comportamento do assistente, incluindo confirmar ação destrutiva. |

### Regras que não cedem a estágio

Independem de quantas pessoas mantêm o projeto:

1. **Nunca `pull_request_target` em workflow.** Esse gatilho dá segredos a código
   vindo de fork. Se alguém precisar de algo que só ele resolve, a resposta é não.
2. **Nenhuma dependência nova sem justificativa escrita no PR.** Este projeto grava
   áudio; o orçamento de confiança é curto.
3. **Mudança em captura, retenção ou envio de áudio exige issue antes do código.**
   Ver `CONTRIBUTING.md`.
4. **Clonagem de voz de pessoa real não entra.** Ver `docs/VOICE_LICENSING.md`.
5. **Segredo nunca em variável de workflow de PR.** Publicação usa Trusted
   Publishing por OIDC, sem token no repositório.

---

## O que impede o projeto de engessar

Robustez sem atrito exige que as coisas chatas andem sozinhas.

**Dependabot com auto-merge** para patch e minor de ferramenta de desenvolvimento,
quando o CI passa. Major e dependência de runtime ficam manuais. Sem isso, o
mantenedor gasta a energia dele em bump de versão em vez de código.

**Um único gate obrigatório: CI verde.** Sem checklist manual, sem aprovação de
comitê, sem "aguardando revisão de arquitetura".

**Auto-merge disponível para qualquer PR.** Autor marca, e o merge acontece quando
o CI fecha. Ninguém espera alguém acordar.

**Resposta em 48 h, mesmo que só para dizer que viu.** O que mata contribuição não
é rejeição, é silêncio.

**Escopo declarado.** `docs/ROADMAP.md` diz o que está no plano e o que não está,
com estimativa honesta de esforço. Contribuidor que sabe onde ajudar não precisa
perguntar.

**Rejeição vem com motivo e alternativa.** "Não vai entrar porque X; o que
resolveria o seu caso é Y."

---

## Versionamento e release

SemVer. Nesta fase, `main` é sempre publicável e release sai quando há motivo, não
por calendário.

Quebra de compatibilidade exige: entrada em `CHANGELOG.md` sob `### Alterado`,
caminho de migração no texto, e bump de major. Variável de ambiente removida
continua sendo lida por uma minor, com aviso.

---

## Como virar mantenedor

Não há formulário. O caminho é o normal: contribuições consistentes, revisão útil
em PR de outras pessoas, e disposição a manter o que você escreveu. Convite parte
de quem já mantém, e é registrado em issue pública.

Sair também é normal e não é abandono. Abra issue, e a linha em `MAINTAINERS.md`
sai. Preferível a manter nome de quem não responde mais — isso engana quem confia
no projeto.

---

## Conduta

[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), Contributor Covenant 2.1, sem
alterações. Relato por advisory privado.
