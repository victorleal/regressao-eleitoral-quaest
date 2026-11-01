# Modelo linear: previsão com priors e estimação com votos

**Victor Rangel · Econometria Fácil**

Uso uma estrutura de regressão linear composicional nas duas etapas. Antes das urnas, faço previsão a priori: os coeficientes são probabilísticos, informados pela Quaest e pelas hipóteses de participação. Depois, ajusto os coeficientes aos votos observados por WLS sem prior. A primeira etapa usa o modelo para prever, mas não estima seus coeficientes a respostas eleitorais do segundo turno. As duas distribuições vêm de procedimentos diferentes, sem uma atualização bayesiana integral entre elas.

## Variáveis e fórmula de previsão

Para cada seção `i`, considero o eleitorado apto do primeiro turno, `N_i`. Ele se divide em cinco grupos:

| Origem `g` | Contagem no primeiro turno |
|---|---|
| `L` | Votos em Lula |
| `F` | Votos em Flávio |
| `O` | Votos nos demais candidatos |
| `BN` | Votos brancos ou nulos |
| `A` | Ausências |

`x_ig` é a contagem da origem `g` dividida por `N_i`. As cinco proporções somam um. Para o destino `d`, a previsão em contagens é:

```math
\widehat{V}_{id}^{(2)}=N_i\sum_g x_{ig}\beta_{gd}.
```

Aqui, `i` é a seção, `g` é a origem no primeiro turno, `d` é o destino no segundo e `beta_gd` é seu coeficiente. O sobrescrito `(2)` identifica o segundo turno. Multiplicar `N_i × x_ig` recupera o tamanho do grupo de origem.

Por exemplo, uma origem com 100 eleitores e coeficiente hipotético de 0,40 para Lula contribui com 40 votos previstos. Posso fazer essa previsão com um coeficiente sorteado de um prior, antes de observar votos do segundo turno. Para ajustá-lo aos votos dessa eleição por WLS, preciso observar as respostas do segundo turno.

Uso coeficientes nacionais, sem efeitos fixos. Não acrescento intercepto porque as cinco proporções já somam um. Os coeficientes descrevem relações entre totais de seções, sem identificar a mudança de voto de cada pessoa.

## Zero urnas: previsão a priori do modelo linear

Uso as transferências declaradas na Genial/Quaest de 21/10/2026, com arquivo disponível em 22/10, antes do segundo turno. A tabela está na [página 19 do relatório](https://quaest.com.br/wp-content/uploads/2026/10/QUAEST9PRESIDENCIAL2110.pdf#page=19).

| Origem declarada | Lula | Flávio | Restante |
|---|---:|---:|---:|
| Lula | 95% | 0% | 5% |
| Flávio | 0% | 94% | 6% |
| Outros candidatos | 37% | 43% | 20% |
| Branco/nulo ou não compareceu | 40% | 36% | 24% |

### Da pesquisa ao sorteio dos coeficientes

Sorteio uma matriz com cinco origens e quatro destinos: Lula, Flávio, branco/nulo e ausência. Cada linha precisa ter proporções positivas que somem um. Uso uma Dirichlet para gerar essas linhas.

Para Outros, suponha, apenas como exemplo, que metade do restante vá para branco/nulo e metade para ausência:

```text
referências = (0,37; 0,43; 0,10; 0,10)
parâmetro de cada destino = 0,5 + 100 × referência
parâmetros da Dirichlet = (37,5; 43,5; 10,5; 10,5)
```

A média inicial do coeficiente para Lula é `37,5 / 102 ≈ 36,76%`. O acréscimo de 0,5 suaviza as taxas e permite valores positivos onde a pesquisa publicou zero. A concentração 100 é uma escolha do modelo, não o tamanho da amostra da Quaest.

Na execução, a divisão do restante varia conforme uma uniforme entre zero e um. A pesquisa reúne branco/nulo e ausência numa origem; uso o mesmo sorteio inicial para ambas, com fatores independentes de realização do apoio, também uniformes entre zero e um. A massa retirada dos votos válidos retorna ao destino branco/nulo ou ausência, conforme a origem.

### Participação e contabilidade

As mudanças entre turnos de 2014, 2018 e 2022 informam distribuições preditivas Student-t para comparecimento e branco/nulo. Há apenas três eleições nesse histórico. Rejeito sorteios de comparecimento fora dos limites físicos e uso IPF, um balanceamento iterativo, para ajustar os totais de válidos, branco/nulo e ausência.

O balanceamento não recebe uma votação desejada para Lula ou Flávio. Preserva a proporção entre os dois dentro de cada origem, mas muda quanto cada grupo contribui para os votos válidos. Os coeficientes finais passaram por essas transformações e já não seguem simplesmente a Dirichlet inicial.

Os candidatos eliminados compartilham a referência da pesquisa, mas suas origens são agregadas somente depois do balanceamento, preservando os totais nacionais.

### De onde saem os 34,63%

O código gera 100.000 cenários de participação e seleciona 10.000 deles, com sementes fixas. Combina-os com os sorteios dos coeficientes e aplica cada matriz às contagens do primeiro turno.

Como a matriz é nacional, somar as origens antes da multiplicação dá o mesmo total que prever seção por seção e depois somar. Em cada cenário, divido os votos previstos de Lula pela soma dos votos previstos dos dois candidatos.

Em 3.463 dos 10.000 cenários, Lula supera 50% dos válidos: daí os 34,63%. A distribuição vem da aplicação do modelo linear aos dados do primeiro turno, com os coeficientes sorteados. Não sorteio diretamente a votação nacional nem ajusto os coeficientes a votos observados do segundo turno nessa etapa. A frequência depende dos priors, das hipóteses de participação e da dispersão escolhida.

É possível prever com priors antes de observar a resposta de uma regressão, como explica a [documentação do Stan](https://mc-stan.org/docs/stan-users-guide/posterior-predictive-checks.html#prior-predictive-checks). Aqui, a distribuição propaga a incerteza dos coeficientes e da participação até os totais projetados. O código não acrescenta um sorteio separado de erro eleitoral nessa etapa; portanto, não se presume que todos os riscos sobre o resultado real estejam cobertos.

## Primeiras urnas e estimação por WLS

Com urnas apuradas, observo os votos dos dois candidatos nas seções do corte. Para cada destino, a resposta é a contagem do segundo turno dividida pelos aptos do primeiro:

```math
y_{id}=\frac{V_{id}^{(2)}}{N_i},\qquad d\in\{L,F\}.
```

Escolho a matriz de coeficientes que minimiza a soma ponderada dos erros quadráticos:

```math
\frac{1}{2}\sum_{i\in\mathcal{O}}w_i
\sum_{d\in\{L,F\}}
\left(y_{id}-\sum_g x_{ig}\beta_{gd}\right)^2.
```

`O` nessa equação é o conjunto das seções observadas, e `w_i = N_i / média dos aptos observados`. Para cada origem, imponho:

```math
\beta_{gL}\geq0,\qquad\beta_{gF}\geq0,\qquad
\beta_{gL}+\beta_{gF}\leq1.
```

A matriz estimada tem cinco origens e duas respostas. O restante reúne branco/nulo e ausência; não estimo sua separação. Não uso pesquisa, sorteios de priors, penalização ou calibração histórica de participação nessa estimação.

O otimizador resolve um problema quadrático convexo com restrições e confere as condições de ótimo. O início do ajuste pontual é uma constante neutra; os bootstraps podem partir desse ponto estimado, sem receber referências da Quaest.

## Bootstrap municipal e votos pendentes

Em cada uma das 600 repetições, sorteio municípios com reposição. Cada município leva todas as suas seções disponíveis no corte. Estimo a regressão novamente e prevejo as pendências. Os votos já contados permanecem fixos na soma nacional, mesmo quando o município fica fora da amostra de estimação.

No corte de menos de 1%, sorteio 330 municípios; no de aproximadamente 2%, 905. Os 600/600 indicam que todas essas reestimações produziram Lula acima de 50%. O bootstrap dos municípios iniciais não cobre automaticamente diferenças dos municípios que ainda faltam.

As médias e os quantis são calculados depois de obter o percentual nacional em cada repetição. A média dos bootstraps é diferente do resultado de uma única regressão: no corte de menos de 1%, são 51,6744% e 51,6877%, respectivamente.

## Como ler os arquivos de coeficientes

Nos NPZ, `beta` guarda todas as matrizes e `beta_media`, sua média. Com zero urnas, são matrizes sorteadas, de dimensão 10.000 × 5 × 4. Com urnas, são matrizes estimadas, de dimensão 600 × 5 × 2.

`beta_pontual` existe somente nos NPZ dos cortes com urnas e contém o ajuste com todos os municípios observados. No CSV, essa coluna fica vazia para zero urnas; `media_cenarios` continua mostrando a média dos sorteios. A coluna `metodo` distingue a simulação da estimação.

## Ordem de chegada das seções

Os arquivos de ordem contêm somas acumuladas das origens do primeiro turno. A ordem usa horários históricos de 2022, a cronologia do primeiro turno de 2026 e a informação conhecida no corte. No corte de menos de 1%, as velocidades relativas das UFs foram fixadas em um; no de aproximadamente 2%, houve seleção de velocidades com contagens do prefixo disponível.

Este pacote recebe a ordem como insumo e recalcula os votos previstos. A incerteza sobre essa ordem não está incluída nos bootstraps. Os dados vieram de extratos finalizados: filtrar pelo horário da primeira totalização não recupera necessariamente antigas versões de votos retificados.

As equações usam os [blocos matemáticos do GitHub](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions). O exemplo da Dirichlet foi escrito como conta numérica, sem a macro que falhou na exibição anterior.

[Voltar ao README](../README.md)
