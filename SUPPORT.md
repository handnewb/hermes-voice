# Onde perguntar

Escolher o canal certo economiza tempo de todos.

| Sua situação | Vá para |
|---|---|
| Não funciona e você acha que é bug | [Issue de bug](../../issues/new?template=bug_report.yml) — **cole a saída de `hermes-voice --doctor`** |
| Dúvida de configuração ou uso | [Discussions](../../discussions) |
| Ideia ou pedido de funcionalidade | [Issue de melhoria](../../issues/new?template=feature_request.yml), depois de ler o [roadmap](docs/ROADMAP.md) |
| Vulnerabilidade de segurança | [Advisory privado](../../security/advisories/new). **Não abra issue pública.** |
| Quer contribuir | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Quer entender como decisões são tomadas | [`GOVERNANCE.md`](GOVERNANCE.md) |

## Antes de abrir qualquer coisa

```bash
hermes-voice --doctor
```

Verifica ambiente, áudio, transcrição, palavra de ativação, VAD, voz, endpoint e
privacidade — com a correção sugerida de cada falha. Resolve a maioria dos casos
sozinho, e a saída **não** contém chaves de API: os segredos são redigidos.

Vale checar também [`docs/VERIFICATION.md`](docs/VERIFICATION.md): partes do
projeto ainda não foram executadas em hardware real, e talvez o que você
encontrou já esteja listado lá.

## O que ajuda numa issue

Sistema operacional, saída do `--doctor`, modo de gatilho, voz em uso, e o log com
`--verbose`. Sem isso a conversa vira dez mensagens para descobrir qual das dez
coisas quebrou.

## Prazo

Resposta em 48 h, mesmo que só para dizer que vi. Um mantenedor, projeto novo — se
passar disso, comente na própria issue.

## O que não é suporte deste projeto

Problema no Hermes Agent em si, no seu endpoint, ou nas engines de terceiros
(Piper, Kokoro, openWakeWord, faster-whisper). Reporte a eles. Se estiver em
dúvida sobre a fronteira, pergunte em Discussions e eu ajudo a localizar.
