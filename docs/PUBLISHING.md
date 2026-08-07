# Runbook de publicação

Instruções executáveis para publicar este projeto. Escrito para ser entregue a um
agente, mas legível por humano.

**Ordem importa.** Os passos 0 e 1 são bloqueantes: uma vez que o histórico
público existe, corrigir vazamento exige reescrever o histórico, e a essa altura
alguém já pode ter clonado.

---

## 0. Decisões que precisam de resposta antes de qualquer comando

Não prossiga sem as quatro.

| Decisão | Padrão neste repositório | Onde muda |
|---|---|---|
| Nome do repositório | `hermes-voice` | `pyproject.toml`, `README.md`, todas as URLs |
| Handle do GitHub | `handnewb` | Idem — 14 ocorrências |
| Licença | Apache-2.0 | `LICENSE`, `pyproject.toml` |
| Publicar no PyPI? | Não (job desabilitado) | `.github/workflows/release.yml`, `if: false` |

Para trocar handle ou nome de repo de uma vez:

```bash
grep -rl 'handnewb/hermes-voice' --include='*.md' --include='*.toml' --include='*.yml' . \
  | xargs sed -i 's|handnewb/hermes-voice|SEU_HANDLE/SEU_REPO|g'
```

Confira o resultado antes de commitar:

```bash
grep -rn 'handnewb' . --include='*.md' --include='*.toml' --include='*.yml' | grep -v '\.git/'
```

### Sobre o nome

Este repositório se chama `hermes-voice` deliberadamente, e não algo derivado de
um personagem de franquia. `jarvis` aparece apenas como **valor padrão de
configuração** da palavra de ativação, porque é keyword nativa do Porcupine.

A distinção é defensável: preferência de usuário num arquivo de config não é
branding. Nomear o projeto e o material de divulgação a partir de um personagem
de franquia é outra coisa, e a exposição cresce quando o repositório é público,
associado ao seu nome e à sua empresa.

Se você quiser nomear diferente de qualquer forma, use o `sed` acima e evite
referência a franquia no nome, na descrição, nos topics e nas capturas de tela.

---

## 1. Verificação de vazamento — BLOQUEANTE

Rode tudo. Cada comando deve sair vazio.

```bash
# a) segredos e chaves
grep -rniE '(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*["'"'"']?[A-Za-z0-9_\-]{16,}' \
  . --include='*.py' --include='*.md' --include='*.yml' --include='*.toml' --include='*.ps1' --include='*.sh'

# b) .env real nao rastreado
test -f .env && echo "ATENCAO: .env existe localmente -- confirme que esta no .gitignore"
git check-ignore -v .env 2>/dev/null || echo "FALHA: .env NAO esta ignorado"

# c) nomes internos, cliente, produto, fornecedor de seguranca
grep -rniE 'oplium|tessera|motiva|senhasegura|cyberark|sentinelone|fortiedr|crowdstrike' . \
  --exclude-dir=.git

# d) IP privado, host interno, string de conexao
grep -rnE '(10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' . --exclude-dir=.git
grep -rniE '\.(corp|internal|local|intra)\b' . --exclude-dir=.git

# e) audio e transcricao
find . -name '*.wav' -o -name '*.mp3' -o -name 'transcripts.log' | grep -v '\.git/'
```

Se **(c)** retornar algo, pare e limpe antes de qualquer commit. Nome de cliente
num repositório público é a forma mais silenciosa de vazar a carteira de uma
consultoria, e nome de fornecedor de EDR divulga a postura defensiva de quem
publicou.

Depois, varredura automatizada:

```bash
pipx run detect-secrets scan > /tmp/secrets.json && python -c "
import json; d=json.load(open('/tmp/secrets.json'))
print('ACHADOS:', d['results'] or 'nenhum')"
```

---

## 2. Verificação de qualidade

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ruff check .                    # deve passar
ruff format --check .           # deve passar
pytest -q                       # 128 testes, todos verdes
python -m build                 # gera sdist e wheel
pipx run twine check dist/*     # metadados validos
hermes-voice --doctor           # bloqueantes de audio sao esperados em container
```

Se `ruff format --check` reclamar, rode `ruff format .` e commite junto.

---

## 3. Histórico limpo desde o primeiro commit

Configure identidade e assinatura **antes** do primeiro commit. Corrigir depois
exige reescrever o histórico.

```bash
git init -b main

# E-mail: use o no-reply do GitHub para nao expor o pessoal no historico publico.
# O numero vem de github.com/settings/emails
git config user.name  "Seu Nome"
git config user.email "ID+handle@users.noreply.github.com"

# Assinatura por SSH -- mais simples que GPG e igualmente valida
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519.pub
git config commit.gpgsign true
git config tag.gpgsign true
```

Registre a chave pública como **Signing Key** em github.com/settings/keys, além
de Authentication Key. São entradas separadas; só a de autenticação não faz o
badge "Verified" aparecer.

```bash
git add .
git status --short          # revise a lista INTEIRA antes de commitar
git commit -m "feat: interface de voz conversacional em pt-BR para o Hermes Agent

Microfone aberto com palavra de ativacao, fim de fala por VAD e sessao que
fecha sozinha. Pipeline encadeado com streaming por sentenca.

- 3 modos de gatilho: wake, console e push-to-talk
- 4 backends de TTS: ElevenLabs, Azure, Piper Python e Piper binario
- Estagio de DSP de presenca com 5 presets
- Autodiagnostico via --doctor
- 128 testes, nenhum exigindo audio, GPU, rede ou chave de API"

git log --show-signature -1 | head -5   # confirme a assinatura
```

---

## 4. Criar o repositório

```bash
gh auth status || gh auth login

gh repo create hermes-voice --public --source=. --remote=origin \
  --description "Voice-enabled personal assistant for Hermes Agent. Open mic with wake word, fully local - no API keys, no accounts, 35 languages." \
  --push
```

Topics — é o principal vetor de descoberta:

```bash
gh repo edit --add-topic hermes-agent,nous-research,voice-assistant,speech-to-text \
  --add-topic text-to-speech,wake-word,whisper,piper-tts,kokoro,vad \
  --add-topic offline-first,local-first,python,portuguese
```

Configuração do repositório:

```bash
gh repo edit --enable-issues --enable-discussions \
  --delete-branch-on-merge --enable-squash-merge \
  --enable-merge-commit=false --enable-rebase-merge=false
```

Habilite os recursos de segurança em Settings → Code security, ou:

```bash
gh api -X PATCH repos/:owner/:repo --field security_and_analysis[secret_scanning][status]=enabled
gh api -X PATCH repos/:owner/:repo --field security_and_analysis[secret_scanning_push_protection][status]=enabled
```

**Push protection é o item que mais importa** — bloqueia o commit que contém
segredo antes de ele sair da sua máquina, em vez de avisar depois.

### Regras de colaboração

Aplicar depois do primeiro CI verde. O detalhe importante: **estas são as regras
do estágio 0**, para um mantenedor. `GOVERNANCE.md` diz o que adicionar em cada
estágio e qual gatilho abre o próximo — não aplique o estágio 1 antes de ter
contribuidor, porque aprovação obrigatória com uma pessoa é auto-aprovação.

```bash
# Merge por squash apenas: um commit por mudança, git bisect utilizável
gh repo edit --enable-squash-merge \
  --enable-merge-commit=false --enable-rebase-merge=false \
  --delete-branch-on-merge

# Auto-merge no nível do repositório: autor marca, merge sai quando o CI fecha.
# É o que evita fila esperando alguém acordar.
gh api -X PATCH repos/:owner/:repo -f allow_auto_merge=true

# Proteção da main -- estágio 0
gh api -X PUT repos/:owner/:repo/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["lint", "build"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
```

`enforce_admins: false` é deliberado no estágio 0: com um mantenedor, admin
travado só cria situação em que ninguém consegue corrigir a `main` quebrada. Vira
`true` no estágio 2.

**Estágio 1** (dois contribuidores recorrentes, ou o primeiro PR em caminho
protegido) — troque o bloco `required_pull_request_reviews` por:

```json
{"required_approving_review_count": 1,
 "require_code_owner_reviews": true,
 "dismiss_stale_reviews": true}
```

E, no mesmo momento, exija aprovação manual de CI para conta nova — é a defesa
contra workflow malicioso vindo de fork:

```
Settings > Actions > General > Fork pull request workflows
  -> "Require approval for first-time contributors"
```

### Rótulos

Poucos e usados vale mais que muitos e ignorados.

```bash
GH_TOKEN=$(gh auth token) pipx run github-label-sync \
  --access-token "$GH_TOKEN" --labels .github/labels.yml OWNER/REPO
```

Dois merecem atenção: **`audio-privacidade`** marca qualquer coisa que toque
captura, retenção ou envio de áudio, e essas exigem issue antes do código.
**`nao-verificado`** marca área listada em `docs/VERIFICATION.md` como nunca
executada — é o rótulo que vai receber mais issue nas primeiras semanas.

### Auto-merge do Dependabot

`.github/workflows/auto-merge.yml` mescla bump de ferramenta de desenvolvimento
quando o CI está verde, e rotula o resto como `revisao-manual`. Nada de runtime
nem major entra sozinho.

Ele roda em `schedule` e não em `pull_request_target`, embora o segundo seja o
padrão difundido. O motivo está no comentário do arquivo: o projeto tem regra
absoluta contra aquele gatilho, e regra que o próprio autor contorna deixa de ser
regra — a próxima pessoa copia o padrão e faz o checkout do código do PR, que é
onde mora a vulnerabilidade.

Confirme que ele existe e roda:

```bash
gh workflow list
gh workflow run "Dependabot auto-merge"    # teste manual
```

## 5. Release

```bash
gh workflow list                       # confirme que CI passou
gh run watch

git tag -s v1.0.0 -m "v1.0.0 -- primeira versao publica"
git push origin v1.0.0                 # dispara release.yml
gh release view v1.0.0
```

---

## 6. Submeter ao Hermes Atlas

Catálogo curado, com revisão de segurança antes da inclusão e curadoria semanal.
Logo: o repositório precisa estar bom **antes**, e a submissão é um pedido.

### Os critérios são dois

1. Ser especificamente construído para ou integrado ao Hermes Agent.
2. Ter sido criado depois de 22 de julho de 2025.

Você atende os dois. **Não há mínimo de estrelas no Atlas**, e esse é o detalhe
que importa: os outros dois diretórios do ecossistema (`get-hermes.ai/community` e
`discoverhermes.com`) exigem 50 estrelas. Comece pelo Atlas; os outros vêm depois,
com tração.

### Antes de abrir a issue: grave a demonstração

O Atlas avalia por documentação, evidência de instalação, manutenção e sinais de
adoção. Dos quatro, o único sobre o qual você tem controle imediato é **evidência
de instalação** — e é justamente o ponto fraco, porque o `docs/VERIFICATION.md`
diz com franqueza que o caminho de áudio nunca foi executado.

Rode o roteiro de verificação manual do `VERIFICATION.md`, corrija o que quebrar,
e então grave:

```bash
pipx run asciinema rec demo.cast --overwrite
#   hermes-voice --doctor
#   hermes-voice voices --lang en
#   hermes-voice --verbose      (fale algumas frases)
# Ctrl+D encerra
pipx run asciinema upload demo.cast
```

Para ferramenta de voz o ideal é **áudio**: trinta segundos em que se ouve a
conversa valem mais que qualquer parágrafo, e é o que decide a estrela. Coloque no
topo do README.

### A submissão

É uma issue com a URL do repositório. O corpo já está escrito em
`docs/atlas-submission.md` — apague o cabeçalho de instruções antes de postar, ele
está marcado.

```bash
gh repo view ksimback/hermes-ecosystem     # confirme a via atual primeiro

gh issue create --repo ksimback/hermes-ecosystem \
  --title "Add: handnewb/hermes-voice — voice-enabled personal assistant" \
  --body-file docs/atlas-submission.md
```

Processo de projeto comunitário muda. Se houver `CONTRIBUTING.md` lá descrevendo
outro formato, siga o de lá em vez deste.

**Categoria provável:** integrações, ou ferramentas de desenvolvedor. Não é skill
pura nem plugin — é uma ferramenta que traz um `SKILL.md`.

### Publicar o SKILL.md como skill

Independente do Atlas, o `SKILL.md` segue o padrão agentskills.io:

```bash
hermes skills publish        # confirme a sintaxe com: hermes skills --help
```

## 7. Depois de publicar

Na primeira semana:

- [ ] Leia `GOVERNANCE.md` e confirme que as regras do estágio 0 estão aplicadas

- [ ] Responda toda issue em 48 h, mesmo que só para dizer que viu
- [ ] Adicione um GIF ou vídeo curto no topo do README — para ferramenta de voz,
      ouvir vale mais que qualquer parágrafo, e é o que decide a estrela
- [ ] Confira o CI no Windows: é onde o `piper-phonemize` e o cuDNN quebram, e
      onde você não vai reproduzir localmente se desenvolve em Linux
- [ ] Fixe as actions em SHA: `pipx run pin-github-action .github/workflows/*.yml`
- [ ] Habilite Dependabot alerts se ainda não estiver ligado

O que **não** fazer: prometer AEC com data. É o item mais pedido e o mais difícil,
e o roadmap já é honesto sobre isso.

---

## Checklist final

```
[ ] Passo 1 inteiro sem achados -- especialmente (c), nomes internos
[ ] .env ignorado, confirmado com git check-ignore
[ ] ruff, pytest e build limpos
[ ] Primeiro commit assinado, com e-mail no-reply
[ ] Handle e nome do repo substituídos em todas as URLs
[ ] Secret scanning e push protection habilitados
[ ] Squash-only, auto-merge do repositório, proteção da main do estágio 0
[ ] Rótulos sincronizados a partir de .github/labels.yml
[ ] CI verde nos três SOs antes da tag
[ ] Tag assinada, release publicado
[ ] Roteiro de verificação manual do VERIFICATION.md executado
[ ] Demonstração gravada e no topo do README
[ ] Submissão ao Atlas só depois de tudo acima
```
