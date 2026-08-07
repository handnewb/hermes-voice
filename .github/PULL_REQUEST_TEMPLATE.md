## O que muda

<!-- Uma ou duas frases. -->

## Por quê

<!-- O problema que isso resolve. Se houver issue, referencie: Closes #N -->

## Como foi verificado

- [ ] `pytest` passa
- [ ] `ruff check .` e `ruff format --check .` limpos
- [ ] `hermes-voice --doctor` sem novos bloqueantes
- [ ] Testado com áudio real (diga qual SO, backend de TTS e modo de gatilho)

## Checklist

- [ ] Nenhuma chave, token, endpoint interno ou nome de cliente no diff
- [ ] Se mudei comportamento de captura, gravação ou retenção de áudio, expliquei abaixo
- [ ] `CHANGELOG.md` atualizado

## Notas sobre privacidade de áudio

<!-- Obrigatório se o PR toca captura, buffer, transcrição ou envio de áudio.
     Se não toca, escreva "não se aplica". -->
