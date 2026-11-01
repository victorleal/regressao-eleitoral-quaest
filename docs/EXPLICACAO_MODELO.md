# Explicação do modelo

Este documento explica, passo a passo, o modelo implementado neste
repositório. A ideia é projetar o resultado do segundo turno a partir da
composição observada no primeiro turno e, depois, atualizar a projeção quando
as primeiras seções do segundo turno são apuradas.

O projeto é uma reconstrução retrospectiva e didática. A especificação foi
escolhida conhecendo o desfecho, portanto os resultados não devem ser
interpretados como uma previsão independente registrada antes da eleição.

## 1. Dados de entrada

O arquivo `dados/primeiro_turno_e_cortes.json` contém os totais nacionais do
primeiro turno, no escopo Brasil sem exterior. O eleitorado é dividido em
cinco origens:

1. eleitores que votaram em Lula;
2. eleitores que votaram em Flávio;
3. eleitores que votaram nos demais candidatos;
4. eleitores que votaram branco ou nulo;
5. eleitores ausentes.

Os CSVs `dados/apuracao_1pct.csv` e `dados/apuracao_2pct.csv` contêm as
seções observadas nos cortes da apuração. Cada linha traz as origens do
primeiro turno e os votos observados de Lula e Flávio no segundo turno.

Os cortes são fotografias parciais, não necessariamente uma amostra aleatória:

| Corte | Seções | Municípios | Horário |
|---|---:|---:|---|
| aproximadamente 1% | 4.208 | 330 | 2026-10-25 19:04:21 |
| aproximadamente 2% | 9.205 | 905 | 2026-10-25 19:16:39 |

Os demais arquivos têm funções distintas:

- `quaest.json`: percentuais publicados de transferência para Lula e Flávio;
- `historico_nacional.csv`: comparecimento e brancos/nulos em 2014, 2018 e
  2022;
- `baseline_2026_1t.csv`: situação observada no primeiro turno de 2026;
- `referencia.json`: valores usados somente para verificar a reprodução.

## 2. Modelo linear de composição

Para cada seção, o primeiro turno fornece cinco quantidades de origem. Para
cada origem `g`, o modelo estima uma proporção de destino `beta`.

Para uma origem com 100 eleitores e coeficiente 0,40 para Lula, a contribuição
esperada para Lula é:

```text
100 × 0,40 = 40 eleitores
```

Somando as contribuições das cinco origens, obtemos a previsão nacional:

```text
previsão de Lula = soma(origem × coeficiente para Lula)
```

O modelo usa os mesmos coeficientes nacionais para todas as seções. Não há
intercepto adicional, efeitos fixos de município ou efeitos fixos de estado.
Como as origens formam uma composição, suas proporções somam um.

## 3. Cenário sem urnas: o prior preditivo

Quando ainda não há votos observados do segundo turno, o código executa
`criar_prior()`. Essa função não estima uma regressão com respostas observadas.
Ela cria 10.000 matrizes possíveis de coeficientes.

### 3.1 Participação

`sortear_participacao()` calcula, a partir de 2014, 2018 e 2022, as mudanças
históricas entre os turnos:

- mudança no comparecimento;
- mudança na proporção de brancos e nulos.

Como há somente três eleições, o código usa uma preditiva Student-t com dois
graus de liberdade. A Student-t tem caudas mais largas que a normal e permite
cenários mais distantes da média histórica.

O código gera 100.000 cenários e seleciona 10.000 sem reposição. Cada cenário
contém:

```text
votos válidos, brancos/nulos, ausências
```

O comparecimento é rejeitado quando fica fora dos limites físicos: abaixo de
zero ou acima do total de eleitores aptos.

### 3.2 Transferências de voto

Para cada linha da Quaest, o código calcula:

```text
restante = 1 - proporção de Lula - proporção de Flávio
```

Por exemplo:

```text
Lula = 37%, Flávio = 43%, restante = 20%
```

O restante é dividido aleatoriamente entre branco/nulo e ausência. Depois, o
código gera uma distribuição Dirichlet para as quatro categorias:

```text
Lula, Flávio, branco/nulo, ausência
```

A Dirichlet é apropriada porque sorteia proporções não negativas que sempre
somam 1. No código, ela é gerada por variáveis Gamma:

```python
gamma = rng.gamma(0.5 + 100 * p)
draw = gamma / gamma.sum(axis=1, keepdims=True)
```

O vetor `p` usa os percentuais da Quaest para Lula e Flávio e uma divisão
sorteada para o restante. O parâmetro `alpha` de cada categoria é:

```text
alpha = 0,5 + 100 × p
```

O `0,5` garante parâmetros positivos; o `100` controla a concentração. Quanto
maior a concentração, mais próximos ficam os sorteios da referência `p`.

### 3.3 Calibração por IPF

Os sorteios de transferência e os cenários de participação precisam ser
compatíveis. `calibrar_participacao()` faz essa reconciliação usando IPF
(*Iterative Proportional Fitting*).

Em cada iteração, o código:

1. ajusta as colunas para bater os totais de válidos, branco/nulo e ausência;
2. ajusta as linhas para preservar o tamanho de cada origem do primeiro turno;
3. repete até os dois conjuntos de totais coincidirem.

A proporção Lula/Flávio dentro dos votos válidos de cada origem é preservada.
Se uma origem tinha 60% Lula e 40% Flávio entre os válidos, aumentar o total
válido dessa origem mantém a divisão 60/40.

Ao final, os 10.000 cenários são aplicados aos totais nacionais do primeiro
turno por `prever()`. Para cada cenário:

```text
votos previstos = origens do primeiro turno × matriz beta
Lula (%) = Lula previsto / (Lula previsto + Flávio previsto)
```

## 4. Resumo da distribuição inicial

Os 10.000 percentuais formam a distribuição da previsão inicial.

- A média é `theta.mean()`.
- O intervalo central de 95% usa os percentis 2,5% e 97,5%.
- A contagem acima de 50% é `(theta > 50).sum()`.

Assim, 3.463 cenários acima de 50% em 10.000 correspondem a:

```text
3.463 / 10.000 = 34,63%
```

Essa frequência é condicional às hipóteses do modelo. Ela não é uma
probabilidade oficial da Quaest nem inclui necessariamente toda a incerteza
sobre o resultado real.

## 5. Com urnas: WLS restrita

Nos cortes de 1% e 2%, o código observa os votos de Lula e Flávio nas seções
disponíveis. A função `atualizar_com_apuracao()` estima os coeficientes por
WLS (*Weighted Least Squares*, mínimos quadrados ponderados).

Para cada seção, compara:

```text
votos observados no segundo turno
vs.
votos previstos pela composição do primeiro turno
```

Seções maiores recebem maior peso porque representam mais eleitores. Sem
ponderação, uma seção pequena teria a mesma influência que uma seção grande.
O peso usado é proporcional ao número de eleitores aptos da seção.

Somente Lula e Flávio são estimados. Branco/nulo e ausência permanecem juntos
no residual porque os dados observados não identificam separadamente essa
divisão. Para cada origem, são impostas as restrições:

```text
beta_Lula >= 0
beta_Flávio >= 0
beta_Lula + beta_Flávio <= 1
```

Essas restrições mantêm os coeficientes dentro de uma interpretação
composicional. A pesquisa Quaest não entra nessa estimação; o ajuste usa os
votos observados do corte.

## 6. Bootstrap municipal

Depois do ajuste pontual, o código faz 600 reestimações. Em cada uma:

1. sorteia municípios com reposição;
2. inclui todas as seções disponíveis de cada município sorteado;
3. reestima a WLS;
4. aplica os coeficientes às seções pendentes;
5. soma os votos já contados, mantidos fixos;
6. calcula a porcentagem nacional final.

Sortear municípios inteiros preserva a possível semelhança entre seções do
mesmo município. Porém, esse bootstrap mede apenas parte da incerteza: ele não
resolve automaticamente diferenças entre os municípios observados e os ainda
pendentes, nem a incerteza da ordem de chegada.

## 7. Trajetória da apuração

Os arquivos `ordem_hipotetica_1pct.csv` e
`ordem_hipotetica_2pct.csv` fornecem uma ordem estimada para a chegada das
seções pendentes. `graficos.py` usa essa ordem para desenhar uma trajetória.

Essa trajetória é uma visualização condicionada à ordem fornecida. O resultado
final não depende da ordem em que as parcelas são somadas; o caminho desenhado
depende.

## 8. Por que essas escolhas?

Algumas decisões vêm diretamente de propriedades matemáticas:

- Dirichlet: proporções que precisam somar 100%;
- WLS: observações com tamanhos diferentes;
- IPF: ajuste simultâneo de totais de linhas e colunas;
- bootstrap: avaliação da variabilidade da estimação;
- Student-t: poucos dados históricos e caudas mais largas.

Outras decisões são escolhas de modelagem:

- usar a Quaest como referência;
- usar concentração 100 na Dirichlet;
- usar dois graus de liberdade na Student-t;
- fazer 10.000 cenários e 600 bootstraps;
- agrupar candidatos menores;
- usar municípios como unidades do bootstrap;
- escolher os cortes e a ordem hipotética.

Essas escolhas devem ser justificadas por teoria, conhecimento do problema,
diagnósticos e comparação com alternativas. Nenhum algoritmo escolhe sozinho a
especificação correta.

## 9. Onde estudar

Uma trilha prática para aprender a construir modelos desse tipo:

1. **Probabilidade e distribuições**
   - distribuições Normal, Student-t, Beta, Gamma e Dirichlet;
   - esperança, variância, quantis e simulação Monte Carlo.

2. **Regressão**
   - mínimos quadrados ordinários;
   - mínimos quadrados ponderados;
   - restrições lineares e problemas de otimização convexa.

3. **Inferência e incerteza**
   - bootstrap;
   - intervalos de confiança;
   - diferença entre intervalo de incerteza e probabilidade do resultado.

4. **Modelos composicionais**
   - dados que somam um total;
   - proporções e transformação de dados;
   - Dirichlet e modelos de mistura.

5. **Modelos hierárquicos e pesquisa eleitoral**
   - efeitos de município e estado;
   - amostragem por conglomerados;
   - viés de seleção e representatividade.

Boas referências:

- [Stan User's Guide: prior e posterior predictive checks](https://mc-stan.org/docs/stan-users-guide/posterior-predictive-checks.html)
- [SciPy: distribuição Dirichlet](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.dirichlet.html)
- [SciPy: distribuição Student-t](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html)
- [SciPy: otimização `minimize`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html)
- Bradley Efron e Robert Tibshirani, *An Introduction to the Bootstrap*
- Andrew Gelman et al., *Bayesian Data Analysis*
- James, Witten, Hastie e Tibshirani, *An Introduction to Statistical Learning*

Para um guia mais amplo sobre quando usar cada distribuição, como construir
priors, escolher um modelo, validar previsões e fazer análise de sensibilidade,
consulte [`GUIA_MODELAGEM_E_DISTRIBUICOES.md`](GUIA_MODELAGEM_E_DISTRIBUICOES.md).

Para estudar este projeto em particular, leia nesta ordem:

1. `README.md`;
2. este arquivo;
3. `docs/METODO.md`;
4. `modelo.py`;
5. `reproduzir.py`;
6. `test_reproducao.py`.

Uma boa prática é alterar uma hipótese por vez — por exemplo, a concentração
da Dirichlet ou o número de graus de liberdade — e observar como a distribuição
final muda. Isso ensina quais conclusões vêm dos dados e quais vêm das escolhas
do modelo.
