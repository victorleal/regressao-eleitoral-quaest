# Uma regressão para acompanhar a apuração

**Victor Rangel · Econometria Fácil**

Uma parcial eleitoral mostra quem já foi contado. Para estimar quem ainda falta, eu preciso de um modelo. Neste exercício, uso o perfil de primeiro turno de cada seção e uma pesquisa de transferência de votos da Quaest. Antes da apuração, o modelo gera cenários a partir desses priors. Quando chegam os primeiros resultados, eu reestimo os coeficientes e projeto as seções pendentes.

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

Instale as três dependências e rode:

```bash
python -m pip install -r requirements.txt
python reproduzir.py --verificar
```

O comando refaz o prior, escolhe a penalização por validação cruzada, estima as regressões e gera tabelas e gráficos em `resultados/`. A opção `--verificar` compara os resultados com a referência **depois de estimar**. Sem essa opção, a referência nem é aberta.

Para estudar uma etapa isolada:

```bash
python reproduzir.py --corte 0 --saida resultados/zero
python reproduzir.py --corte 1 --saida resultados/um
python reproduzir.py --corte 2 --saida resultados/dois
```

`--corte 0` funciona mesmo sem os dois arquivos de apuração. `--corte 1` não abre o arquivo de 2%. Os testes verificam isso:

```bash
python -m unittest -v
```

## O que deve aparecer

O placar considera **Brasil sem exterior**. Os cortes de 1% e 2% são definidos pelo avanço nacional, incluindo o exterior, e preservam o último lote completo antes do limite.

| Informação disponível | Seções domésticas | Média de Lula nos válidos | Faixa central de 95% dos cenários | Cenários acima de 50% |
|---|---:|---:|---:|---:|
| Zero urnas | 0 | 49,47% | 45,65%–53,65% | 3.463/10.000 = 34,63% |
| ≈1% nacional | 4.208 | 51,67% | 51,28%–51,97% | 600/600 |
| ≈2% nacional | 9.205 | 51,64% | 51,29%–51,94% | 600/600 |

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
- $d$: destino no segundo turno — Lula, Flávio, branco/nulo ou ausência.
- $\beta_{gd}$: coeficiente da origem $g$ para o destino $d$.
- $\widehat V_{2id}$: quantidade prevista de votos ou ausências no destino $d$.

É linear nos coeficientes. A matriz $\beta$ tem **5 linhas e 4 colunas**, com coeficientes positivos e soma 1 em cada linha. Não adiciono intercepto: as parcelas de origem já somam 1. Não há efeitos fixos de município ou UF. O município serve para separar os grupos na validação cruzada e no bootstrap.

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

Eu estimo a matriz minimizando:

$$
\frac12\sum_{i\in\mathcal A}w_i
\sum_{d\in\{L,F\}}\left(y_{id}-\sum_gx_{ig}\beta_{gd}\right)^2
+\lambda\sum_{g,d}\mu_{gd}\log\frac{\mu_{gd}}{\beta_{gd}},
$$

sujeito a $\beta_{gd}>0$ e $\sum_d\beta_{gd}=1$.

Aqui, $\mathcal A$ é o conjunto de seções já apuradas; $w_i=N_i/\overline N$ é o peso por eleitorado; $\mu$ é a matriz de referência do prior; e $\lambda$ controla o peso da penalização. O primeiro termo é o erro de uma regressão ponderada. O segundo cobra um custo quando os coeficientes se afastam do prior.

Para quem vem da econometria frequentista, é útil pensar nisso como **mínimos quadrados com restrições e uma penalização informada pela pesquisa**. Eu escolho $\lambda$ por validação cruzada de cinco grupos de municípios, usando somente as seções disponíveis no corte. Nos dois cortes, a grade seleciona **0,001**.

Os destinos branco/nulo e ausência permanecem latentes: não crio respostas fictícias para eles. O ajuste usa apenas as respostas Lula/Flávio.

Para representar variação, faço 600 reamostragens dos municípios observados. Cada uma recebe uma matriz do prior e reestima os coeficientes. O valor de $\lambda$ fica fixo no selecionado pela validação. **Isso é uma combinação de prior e bootstrap, não uma amostra de um posterior bayesiano completo.** As faixas das tabelas descrevem esses cenários, não intervalos de confiança frequentistas ou cobertura eleitoral validada.

## Da regressão ao placar nacional

Eu mantenho fixos os votos já contados. Só os pendentes são estimados:

$$
\widehat V_{2d}^{\mathrm{total}}=
V_{2d}^{\mathrm{contado}}+
\sum_{i\notin\mathcal A}N_i\sum_gx_{ig}\widehat\beta_{gd}.
$$

Divido o total previsto de Lula pela soma dos totais de Lula e Flávio em cada cenário. A média e as faixas são calculadas **depois dessa divisão**, preservando a distribuição dos percentuais.

## E as curvas que se cruzam?

![Trajetória projetada com o corte de 2%](figuras/trajetoria.png)

Resultado final e ordem de chegada são problemas diferentes. Para desenhar uma trajetória, preciso supor quais seções pendentes entrarão primeiro.

O arquivo `ordem_hipotetica_origens.csv` traz apenas as somas acumuladas das cinco origens do **primeiro turno**, em uma ordem hipotética congelada no projeto original. Ela foi construída com cronologia histórica de 2022, horários do primeiro turno de 2026 e informações disponíveis no corte. Não contém votos futuros do segundo turno.

Este projeto enxuto **recebe essa ordem como insumo; não reestima sua seleção**. Recalcula todos os votos previstos e os acumula nessa ordem. A curva depende dessa hipótese e não deve ser apresentada como previsão exata do momento da virada. Já o percentual final independe da ordem de soma.

## Onde olhar no código

| Arquivo | O que faz |
|---|---|
| `reproduzir.py` | Lê os dados de cada etapa, executa as contas e salva as tabelas |
| `modelo.py` | Sorteia o prior, calibra participação, estima a regressão e prevê votos |
| `graficos.py` | Desenha distribuições e trajetória dos resultados recalculados |
| `test_reproducao.py` | Testa isolamento dos cortes e rejeição de horários futuros |
| `referencia.json` | Números publicados, usados apenas pela opção `--verificar` |
| `dados/` | Cerca de 1 MB de extratos e identificação das fontes |

Em `resultados/`, veja `previsoes.csv`, `coeficientes.csv`, `validacao_cruzada_1pct.csv`, `validacao_cruzada_2pct.csv`, os cenários individuais e os gráficos PNG/SVG. Os arquivos NPZ guardam as matrizes recalculadas.

Os dados eleitorais são extratos atribuídos ao TSE; a pesquisa é atribuída à Quaest. As URLs e os hashes estão em `dados/fontes.json`. A licença MIT cobre o código de minha autoria; não transfere direitos sobre os materiais das fontes.
