# Política de segurança

## Reportar vulnerabilidade

Não abra issue pública. Use
[Security Advisories](https://github.com/handnewb/hermes-voice/security/advisories/new).

Resposta em até 5 dias úteis. Se você não tiver retorno nesse prazo, abra uma
issue dizendo apenas que existe um advisory pendente — sem detalhes técnicos.

Divulgação coordenada: 90 dias ou até haver correção publicada, o que vier
primeiro. Crédito no CHANGELOG se você quiser.

## Escopo

Este projeto captura áudio de microfone continuamente, transcreve fala,
fala com um endpoint de LLM e reproduz áudio. A superfície que interessa:

**Em escopo**
- Vazamento de áudio ou transcrição para disco, log ou rede fora do configurado
- Contorno das garantias de retenção descritas em "Modelo de privacidade"
- Injeção via texto transcrito ou via resposta do LLM que resulte em execução
- Exposição de credencial em log, mensagem de erro, saída do `--doctor` ou crash
- Confusão de dependência, typosquatting nos extras, ou artefato de release adulterado

**Fora de escopo**
- Vulnerabilidades nos serviços de terceiros (Picovoice, Azure, ElevenLabs) —
  reporte a eles
- Falsos positivos ou negativos da palavra de ativação (é qualidade de modelo)
- Que o EDR bloqueie o processo (é o EDR fazendo o trabalho dele)

## Modelo de privacidade

Três garantias implementadas em `session.py`, por construção e não por
configuração — não é possível desligá-las por engano:

1. **Em estado `DORMANT` nada é transcrito.** Os frames alimentam apenas o
   detector de palavra de ativação, que roda local e não produz texto.
2. **O pré-roll é um `deque` com `maxlen` fixo** de 480 ms. Há teste que alimenta
   64 segundos de áudio contínuo e verifica que só 480 ms permanecem retidos.
3. **Ao voltar para `DORMANT` o buffer é descartado explicitamente.** Também
   testado, inclusive no caso de já estar em `DORMANT`.

Nada toca o disco a menos que você defina `LOG_TRANSCRIPTS=1`, que é `0` por
padrão e aparece como aviso no `--doctor`.

Se `TTS_BACKEND` for `azure` ou `elevenlabs`, o **texto** da resposta sai para o
provedor. O áudio do seu microfone não sai em nenhuma configuração. Use Piper
para manter tudo local — é o padrão.

## Credenciais

- `.env` está no `.gitignore`. Confira antes do primeiro commit.
- `Config.redacted()` existe para log e para o `--doctor`. Há teste que injeta um
  segredo conhecido e falha se ele aparecer na saída.
- Restrinja a chave no provedor: escopo mínimo, cota de crédito, allowlist de IP.
- Chave de terceiro com custo associado pertence a um cofre, não a um arquivo de
  texto. O `.env` serve para desenvolvimento.

## Superfície de detecção por EDR

Este projeto exibe três comportamentos que motores de EDR comportamental
monitoram legitimamente. Não há nada malicioso aqui, mas o comportamento
observável é indistinguível de spyware, e o alerta é **esperado**:

| Comportamento | Risco | Mitigação |
|---|---|---|
| Hook global de teclado (`pynput`, modo `ptt`) | Alto — assinatura de keylogger | `--trigger wake` ou `--trigger console`. Nenhum dos dois instala hook. |
| Captura contínua de microfone (modo `wake`) | Médio | `--trigger console` grava só sob comando |
| DLL nativa (ctranslate2, onnxruntime, CUDA) | Baixo | Geralmente só lentidão no startup |

Prefira trocar de modo de gatilho a pedir exclusão. Enfraquecer a postura do
endpoint para rodar um assistente de voz é uma troca ruim.

## Cadeia de suprimentos

- Dependências com faixa de versão explícita no `pyproject.toml`
- Dependabot semanal para pip e GitHub Actions
- CodeQL com `security-extended`, semanal e em cada PR
- Gitleaks no CI, em todo o histórico
- Releases via Trusted Publishing (OIDC), sem token de API no repositório

**Pendência conhecida:** as actions estão fixadas em tag (`@v4`), não em SHA.
Fixar em SHA é mais correto. Para fazer:

```bash
pipx run pin-github-action .github/workflows/*.yml
```
