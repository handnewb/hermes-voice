# Script de avaliação de voz — registro Hermes/mordomo (pt-BR)

Texto original, escrito para este projeto. Não é diálogo transcrito de filme, o
que significa que você pode usar comercialmente, publicar comparativos e mandar
para fornecedor sem passivo.

**Como usar.** Cole `script_avaliacao_voz.txt` (versão sem anotação) no
ElevenLabs, Azure Speech Studio ou Piper e gere com cada voz candidata. Ouça na
ordem. Depois ouça só o bloco 6 de cada candidato em sequência — é onde as vozes
ruins se revelam.

**O que cada bloco testa** está anotado abaixo. Não cole os títulos: o TTS lê.

---

## Bloco 1 — Abertura e ironia seca

Testa: registro base, naturalidade em frase curta, ritmo de humor contido. Se a
voz soar entusiasmada aqui, descarte.

> Bom dia, senhor. São seis e quarenta e dois. O senhor dormiu quatro horas e
> dezenove minutos. Eu registrei o número, mas não vou comentá-lo.

## Bloco 2 — Relatório com números falados

Testa: números longos por extenso, que é o que a persona realmente produz.
Cadência de enumeração sem soar como lista.

> Durante a noite o centro de operações processou cento e quarenta e sete mil
> eventos. Três foram escalados e nenhum exigiu sua atenção. O restante fechou
> sozinho, como deveria.

## Bloco 3 — Números crus, siglas e estrangeirismos

Testa: o normalizador do TTS, não a persona. Se o modelo falhar aqui, você sabe
que precisa pré-normalizar no código antes de sintetizar.

> Relatório de conformidade: a ISO 27001 exige revisão anual, a LGPD não fixa
> prazo, e o certificado vence em 03/12/2026. O dashboard mostra 99,7% de
> disponibilidade. O playbook de firewall rodou 1.482 vezes.

## Bloco 4 — Cobertura fonética

Testa: nasais (ã, õ, ãe), dígrafos lh e nh, r em posição inicial, medial e
travada, sândi de sibilante. É o bloco mais chato de ouvir e o mais diagnóstico.

> Amanhã de manhã o trabalho inclui três reuniões, uma conferência e o relatório
> do conselho. As informações já estão organizadas. Não haverá exceções, e o
> senhor não perguntou, mas eu responderia que também não haverá atrasos.

## Bloco 5 — Alerta e urgência contida

Testa: se a voz consegue soar urgente sem levantar o tom. Jarvis nunca grita.

> Senhor, temos uma anomalia. A estação nove-quatro-dois abriu conexão com um
> domínio registrado há dezoito horas. Isolei preventivamente. O senhor pode
> reverter, mas eu não recomendaria.

## Bloco 6 — Frase longa e subordinada

Testa: consistência de prosódia sob carga, controle de respiração, se a voz
degrada no fim. É aqui que TTS mediano se desmonta.

> O senhor me perguntou ontem se a automação do fluxo de identidade poderia
> operar sem aprovação humana nos casos padrão, e a resposta continua sendo que
> pode, desde que a política permaneça com quem tem autoridade para respondê-la,
> e não comigo, porque a distinção entre operar e governar é a única coisa que
> impede este arranjo de se tornar um problema seu.

## Bloco 7 — Confirmação de ação destrutiva

Testa: peso e pausa. Precisa soar como freio, não como formalidade.

> Antes de prosseguir. Isso vai revogar as credenciais de quatrocentos e doze
> usuários, e é irreversível. Preciso da sua confirmação em voz alta.

## Bloco 8 — Recusa

Testa: firmeza sem hostilidade. A voz precisa conseguir dizer não.

> Não, senhor. Eu não leio segredo em voz alta, nem quando o senhor pede. O ar
> desta sala não tem controle de acesso.

## Bloco 9 — Incerteza

Testa: naturalidade em frase curta e reta, sem hesitação artificial.

> Não sei, senhor. Posso apurar, mas não vou inventar para preencher o silêncio.

## Bloco 10 — Perguntas e entonação

Testa: contorno interrogativo, que é onde vozes sintéticas soam mais falsas.
Ouça as três em sequência.

> Detalho? O senhor quer que eu prossiga? Devo isolar a máquina agora?

## Bloco 11 — Encerramento

Testa: cadência descendente, fechamento. Deve soar como fim, não como corte.

> Boa noite, senhor. Vou reduzir a iluminação e continuar monitorando. Se algo
> mudar, o senhor será o primeiro a saber. E se nada mudar, eu não o acordarei
> para dizer isso.

---

## Critérios de julgamento

Ouça na ordem e pontue de um a cinco. Descarte a candidata que falhar em
qualquer um dos três primeiros — os outros são refináveis, esses não.

1. **Não soa animada.** Eliminatório. A maioria das vozes comerciais de pt-BR é
   treinada para atendimento e vem com sorriso embutido.
2. **Aguenta o bloco 6 sem degradar.** Eliminatório.
3. **Consegue dizer não (bloco 8) sem soar agressiva nem submissa.** Eliminatório.
4. Nasais do bloco 4 limpas, sem metalizar.
5. Bloco 3 normalizado corretamente, ou pelo menos de forma previsível.
6. Perguntas do bloco 10 com contorno crível.
7. Consistência de timbre entre bloco 1 e bloco 11.

## Depois de escolher

O timbre é metade. A outra metade é o processamento — corte de graves, compressão
e um toque de reverb de sala é o que faz a voz soar como presença no ambiente em
vez de locução. Nenhum TTS entrega isso de fábrica. Ver `docs/ROADMAP.md`.
