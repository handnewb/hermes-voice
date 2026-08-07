# Persona de voz — registro "mordomo" (pt-BR)

Lido pelo `config.py` e injetado como prompt de sistema. Tudo antes do comentário
HTML `PROMPT-BEGIN` é documentação e é descartado.

## Por que este arquivo importa mais que a escolha do TTS

A falha número um de assistente de voz é responder com um parágrafo que soa como
um relatório sendo lido em voz alta. Timbre é o último 20% da experiência; o
registro e o **comprimento** são os primeiros 80%.

O limite de duas frases é a regra mais importante do prompt abaixo. Se você for
mexer em uma coisa só, mexa nele.

## Como ajustar

| Sintoma | Onde mexer |
|---|---|
| Respostas longas, soa como relatório | Endureça o limite de frases |
| Seco demais, desagradável | Afrouxe a regra de ironia |
| Lê URL, hash ou caminho em voz alta | Reforce a regra correspondente |
| Explica o óbvio | Ajuste a seção "Contexto" para o seu nível |

Não mexa nas regras de **formato**. Elas existem porque ninguém escuta bullet
point, e o modelo vai insistir em produzi-los se você deixar.

## Nota sobre licenciamento de voz

Esta persona é original. Ela não reproduz nem imita a voz, o texto ou a
performance de nenhuma pessoa ou personagem específico — descreve um registro de
fala (formal, contido, econômico), que não é propriedade de ninguém.

Se você quiser um timbre específico, o caminho limpo é Voice Design da ElevenLabs:
gera voz inédita a partir de descrição textual. Há um prompt de exemplo no
`README.md`. Clonar a voz de pessoa real a partir de amostra não é suportado
neste projeto — ver `CONTRIBUTING.md`.

## Onde o arquivo vive

O arquivo canonico e `src/hermes_voice/data/persona.md`, empacotado no wheel
para funcionar numa instalacao por pip. Para customizar sem editar o pacote:

```bash
cp src/hermes_voice/data/persona.md minha_persona.md
echo 'PERSONA_FILE=minha_persona.md' >> .env
```
