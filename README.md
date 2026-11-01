# Uma regressão para acompanhar a apuração

**Victor Rangel · Econometria Fácil**

Uma parcial eleitoral mostra quem já foi contado. Para estimar quem ainda falta, eu preciso de um modelo. Neste exercício, uso o perfil de primeiro turno de cada seção e uma pesquisa de transferência de votos da Quaest. Antes da apuração, o modelo gera cenários a partir desses priors. Quando chegam os primeiros resultados, estimo uma regressão ponderada sem prior e projeto as seções pendentes.

Este repositório é a versão pequena e reproduzível do meu artigo: **três arquivos Python, dados em CSV e um comando**. Os coeficientes são recalculados; as previsões publicadas não entram no ajuste.

É uma **reconstrução retrospectiva de 2026**, com código próprio. A especificação foi escolhida depois da eleição. Os horários permitem limitar os votos aos cortes de informação, mas os extratos vieram de arquivos finais, não de snapshots arquivados ao vivo. Portanto, este exercício não demonstra desempenho prospectivo nem recupera exatamente o algoritmo de Rodrigo Mahlmeister.

## Rodar

Use Python **3.12 ou mais recente**. Não precisa de chave de API, conta em serviço externo ou download dos microdados completos.

```bash
git clone https://github.com/vr-rodrigues/regressao-eleitoral-quaest.git
cd regressao-eleitoral-quaest
python -m venv .venv
```

Ative o ambiente:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Instale as quatro dependências e rode:

```bash
python -m pip install -r requirements.txt
python reproduzir.py --verificar
```

O comando refaz a simulação com zero urnas, estima as regressões sem prior e gera tabelas e gráficos em `resultados/`. A opção `--verificar` compara os resultados com a referência **depois de estimar**. Sem essa opção, a referência nem é aberta.

Para estudar uma etapa isolada:

```bash
python reproduzir.py --corte 0 --saida resultados/zero
python reproduzir.py --corte 1 --saida resultados/um
python reproduzir.py --corte 2 --saida resultados/dois
```

`--corte 0` funciona mesmo sem os dois arquivos de apuração. `--corte 1` não abre o arquivo de 2%, a pesquisa Quaest nem o histórico de participação. A etapa com urnas funciona sem esses arquivos. Os testes verificam isso:

```bash
python -m unittest -v
```

## O que deve aparecer

O placar considera **Brasil sem exterior**. Os cortes de 1% e 2% são definidos pelo avanço nacional, incluindo o exterior, e preservam o último lote completo antes do limite.

| Informação disponível | Seções domésticas | Média de Lula nos válidos | Faixa central de 95% dos cenários | Cenários acima de 50% |
|---|---:|---:|---:|---:|
| Zero urnas | 0 | 49,47% | 45,65%–53,65% | 3.463/10.000 = 34,63% |
| ≈1% nacional | 4.208 | 51,67% | 51,28%–51,98% | 600/600 |
| ≈2% nacional | 9.205 | 51,65% | 51,30%–51,95% | 600/600 |

Horários do TSE: **25/10/2026 às 19:04:21** e **19:16:39**, respectivamente. Os arquivos contêm apenas as seções observadas até cada corte. Não há votos posteriores a 2% nem resultado final no pacote.

**600/600 não significa certeza.** É a frequência em um conjunto de cenários condicionado ao modelo. O bootstrap dos municípios observados não mede todo o risco de extrapolar para lugares que ainda não apuraram.

![Distribuições produzidas pela execução](figuras/distribuicoes.png)

Os painéis usam escalas horizontais diferentes para mostrar a concentração após a apuração. O gráfico de zero urnas mostra um recorte do eixo; as estatísticas usam os 10.000 cenários completos, incluindo as caudas fora da figura.

## A regressão, sem mistério

Cada linha do banco é uma seção eleitoral. Eu divido seus eleitores aptos em cinco origens no primeiro turno:

| Símbolo | Contagem na seção $i$ |
|---|---|
| $L_{1i}$ | Votos em Lula no primeiro turno |
| $F_{1i}$ | Votos em Flávio no primeiro turno |
| $O_{1i}$ | Votos nos outros candidatos no primeiro turno |
| $BN_{1i}$ | Votos brancos ou nulos no primeiro turno |
| $A_{1i}$ | Ausências no primeiro turno |
| $N_i$ | Soma das cinco origens: eleitores aptos no primeiro turno |

O índice **1** marca o primeiro turno. O índice **2**, abaixo, marca o segundo. Para cada origem $g$, defino $x_{ig}$ como sua contagem dividida por $N_i$. Por isso, as cinco parcelas de cada seção somam 1.

Para o destino $d$ no segundo turno, a previsão é:

$$
\widehat V_{2id}=N_i\sum_{g=1}^{5}x_{ig}\beta_{gd}.
$$

- $i$: seção eleitoral.
- $g$: grupo de origem no primeiro turno.
- $d$: destino no segundo turno. Na simulação inicial são quatro destinos: Lula, Flávio, branco/nulo ou ausência. Na regressão com urnas, são as duas respostas Lula e Flávio.
- $\beta_{gd}$: coeficiente da origem $g$ para o destino $d$.
- $\widehat V_{2id}$: quantidade prevista de votos ou ausências no destino $d$.

É linear nos coeficientes. Com zero urnas, sorteio uma matriz $\beta$ com **5 linhas e 4 colunas**, coeficientes positivos e soma 1 em cada linha. Depois dos primeiros votos, estimo uma matriz **5×2**, com as restrições descritas abaixo. Não adiciono intercepto: as parcelas de origem já somam 1. Não há efeitos fixos de município ou UF. O município define os grupos do bootstrap; não faço validação cruzada de uma penalização nesta versão sem prior.

Esses são **coeficientes ecológicos**. Dados agregados por seção não identificam a decisão individual de cada eleitor.

## Como a Quaest vira prior

A pesquisa usada fornece estas intenções de transferência:

| Origem no primeiro turno | Lula | Flávio | Restante |
|---|---:|---:|---:|
| Lula | 95% | 0% | 5% |
| Flávio | 0% | 94% | 6% |
| Outros candidatos | 37% | 43% | 20% |
| Branco, nulo ou não foi votar | 40% | 36% | 24% |

O [relatório da Quaest](https://quaest.com.br/wp-content/uploads/2026/10/QUAEST9PRESIDENCIAL2110.pdf), página 19, é identificado nos dados. A divulgação é de 21/10, com arquivo disponível em 22/10, antes do segundo turno.

Eu não trato essas taxas como coeficientes conhecidos. Sorteio valores próximos delas. Por exemplo, para Outros, suponha que um sorteio divida o restante igualmente entre branco/nulo e ausência. O vetor seria $(0{,}37;0{,}43;0{,}10;0{,}10)$. Então:

$$
\beta_{O,\cdot}\sim\operatorname{Dirichlet}(37{,}5;43{,}5;10{,}5;10{,}5).
$$

Os parâmetros vêm de $\alpha_d=0{,}5+100p_d$. A média inicial do coeficiente de Lula nessa linha é $37{,}5/102\approx36{,}76\%$, não exatamente 37%, por causa da suavização.

Na execução, a divisão do restante também varia: uso uma uniforme entre 0 e 1. O grupo misto branco/nulo/ausência recebe o mesmo sorteio inicial, mas branco/nulo e ausentes têm fatores independentes de realização do apoio, também uniformes entre 0 e 1. A parcela de apoio que não se realiza retorna à origem correspondente.

Depois, calibro os totais de **votos válidos, brancos/nulos e ausências** usando as mudanças entre turnos de 2014, 2018 e 2022. Uso distribuições preditivas Student-t e ajusto as margens por IPF. Essa etapa não impõe um total de votos para Lula ou Flávio. Os coeficientes finais já não seguem a Dirichlet inicial: passaram por essas transformações.

Aplico cada uma das **10.000 matrizes sorteadas** às contagens do primeiro turno. Em **3.463** cenários, Lula passa de 50% dos votos válidos. Daí saem os **34,63%**.

Com zero urnas, não há respostas observadas do segundo turno para ajustar a regressão. Há uma **distribuição preditiva a priori** da relação linear: vario os coeficientes e calculo o que cada matriz prevê.

A concentração **100 é uma escolha minha**, não o tamanho amostral da Quaest. Os fatores uniformes e a hipótese de estabilidade histórica também são escolhas. Os 34,63% pertencem a esse conjunto de hipóteses; não são uma probabilidade divulgada pela pesquisa.

## O que muda quando chegam votos

Com seções apuradas, passam a existir respostas observadas: $y_{id}=V_{2id}/N_i$, para $d$ igual a Lula ou Flávio. O denominador continua sendo o eleitorado apto do primeiro turno.

**Nesta etapa, não uso Quaest, sorteios de priors, calibração de participação ou penalização.** Estimo os coeficientes apenas com os resultados disponíveis no corte, por mínimos quadrados ponderados:

$$
\widehat\beta=\arg\min_\beta
\frac12\sum_{i\in\mathcal A}w_i
\sum_{d\in\{L,F\}}\left(y_{id}-\sum_gx_{ig}\beta_{gd}\right)^2,
$$

sujeito a $\beta_{gL}\geq0$, $\beta_{gF}\geq0$ e $\beta_{gL}+\beta_{gF}\leq1$ em cada origem.

Aqui, $\mathcal A$ é o conjunto de seções já apuradas e $w_i=N_i/\overline N$ é o peso por eleitorado. São cinco explicativas e duas respostas. As restrições impedem votos negativos ou que a soma dos dois candidatos exceda os aptos. Não há parâmetro de penalização nem seleção de lambda. O ponto inicial do otimizador é uma constante neutra, sem depender de pesquisa eleitoral.

A matriz estimada tem **5 linhas e 2 colunas**. O que sobra em cada origem representa branco/nulo e ausência juntos; sem respostas desses destinos, não tento estimar sua separação. Isso difere da simulação com zero urnas, que usa uma matriz de quatro destinos construída a partir de hipóteses.

Para representar variação amostral, faço **600 reamostragens dos municípios observados**, mantendo juntas as seções de cada município, e estimo a mesma regressão em cada uma. Os 600 coeficientes vêm desse bootstrap municipal, sem combinar cada ajuste com um prior. A distribuição inicial de 10.000 cenários e essa distribuição de 600 reajustes são procedimentos diferentes, não uma atualização bayesiana entre si.

A faixa de 95% resume os quantis dos bootstraps. O conjunto de municípios que chegou cedo não é uma amostra aleatória do país, então essa dispersão não cobre automaticamente o risco de extrapolar para locais ainda ausentes.

### Nota sobre a revisão do método

Na primeira versão, eu mantinha o prior da Quaest também depois das primeiras urnas, como penalização no ajuste. Testei sua retirada e as previsões ficaram praticamente iguais: com cerca de 1% nacional, a média foi de 51,671% para 51,674%; com cerca de 2%, de 51,643% para 51,645%. Nesse teste, os dados observados já dominavam a previsão nacional. Por isso, deixei a Quaest apenas na simulação com zero urnas e simplifiquei a estimação após os primeiros votos. Registro a mudança para preservar a comparação com a versão anterior; ela não representa um ganho relevante de acurácia.

## Da regressão ao placar nacional

Eu mantenho fixos os votos já contados. Só os pendentes são estimados:

$$
\widehat V_{2d}^{\mathrm{total}}=
V_{2d}^{\mathrm{contado}}+
\sum_{i\notin\mathcal A}N_i\sum_gx_{ig}\widehat\beta_{gd}.
$$

Divido o total previsto de Lula pela soma dos totais de Lula e Flávio em cada cenário. A média e as faixas são calculadas **depois dessa divisão**, preservando a distribuição dos percentuais.

## E as curvas que se cruzam?

![Trajetória projetada com o corte de menos de 1%](figuras/trajetoria.png)

Resultado final e ordem de chegada são problemas diferentes. Para desenhar uma trajetória, preciso supor quais seções pendentes entrarão primeiro.

Os arquivos `ordem_hipotetica_1pct.csv` e `ordem_hipotetica_2pct.csv` trazem apenas as somas acumuladas das cinco origens do **primeiro turno**, em uma ordem hipotética congelada no projeto original. Ela foi construída com cronologia histórica de 2022, horários do primeiro turno de 2026 e informações disponíveis em cada corte. No de 1%, as velocidades relativas foram fixadas em 1; no de 2%, houve seleção de velocidades usando contagens do prefixo. Não contém votos futuros do segundo turno.

Este projeto enxuto **recebe essa ordem como insumo; não reestima sua seleção**. Recalcula todos os votos previstos e os acumula nessa ordem. A curva depende dessa hipótese e não deve ser apresentada como previsão exata do momento da virada. Já o percentual final independe da ordem de soma.

## Onde olhar no código

| Arquivo | O que faz |
|---|---|
| `reproduzir.py` | Lê os dados de cada etapa, executa as contas e salva as tabelas |
| `modelo.py` | Simula zero urnas com Quaest; estima WLS sem prior nos cortes com urnas |
| `graficos.py` | Desenha distribuições e trajetória dos resultados recalculados |
| `test_reproducao.py` | Testa isolamento dos cortes e rejeição de horários futuros |
| `referencia.json` | Números publicados, usados apenas pela opção `--verificar` |
| `dados/` | Cerca de 1 MB de extratos e identificação das fontes |

Em `resultados/`, veja `previsoes.csv`, `coeficientes.csv`, os cenários individuais e os gráficos PNG/SVG das distribuições e das duas trajetórias. Os arquivos NPZ guardam as matrizes recalculadas.

Os dados eleitorais são extratos atribuídos ao TSE; a pesquisa é atribuída à Quaest. As URLs e os hashes estão em `dados/fontes.json`. A licença MIT cobre o código de minha autoria; não transfere direitos sobre os materiais das fontes.
