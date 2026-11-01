# Guia prático: distribuições, priors e modelagem

Este guia explica como pensar antes de escolher uma distribuição ou escrever
uma regressão. A pergunta principal não é “qual distribuição é mais famosa?”,
mas:

> Que tipo de objeto estou modelando, quais valores são possíveis e de onde
> vem a incerteza?

## 1. Comece pelo objeto observado

Antes da distribuição, identifique a variável:

| Objeto | Exemplos | Distribuições candidatas |
|---|---|---|
| Quantidade inteira | número de votos, chegadas, defeitos | Poisson, binomial negativa |
| Proporção entre 0 e 1 | comparecimento, taxa de conversão | Beta |
| Várias proporções que somam 1 | destinos do eleitorado | Dirichlet |
| Resultado contínuo sem limite fixo | erro, renda transformada | Normal, Student-t |
| Escolha entre categorias | voto em Lula/Flávio/outro | Bernoulli, binomial, multinomial |
| Tempo até um evento | sobrevivência, duração | exponencial, Weibull, log-normal |

Essa tabela é um ponto de partida, não uma regra automática. A distribuição
deve ser compatível com o processo que gerou os dados.

## 2. Distribuições importantes

### Bernoulli e binomial

Use Bernoulli para uma única tentativa com dois resultados, como “Lula vence
ou não vence” em uma simulação. Use binomial para contar sucessos em `n`
tentativas:

```text
votos em Lula ~ Binomial(eleitores válidos, probabilidade de Lula)
```

Isso é apropriado quando as tentativas podem ser tratadas como semelhantes e
há uma probabilidade comum. Se os eleitores têm probabilidades muito
diferentes ou existem grupos, um modelo hierárquico pode ser melhor.

### Beta

A Beta modela uma única proporção entre 0 e 1:

```text
taxa de comparecimento ~ Beta(alpha, beta)
```

Use-a quando a variável é uma proporção contínua e não é necessário modelar
explicitamente o número de tentativas. Para contagens conhecidas, a binomial
com uma distribuição Beta para sua probabilidade leva ao modelo beta-binomial.

### Dirichlet

A Dirichlet é a generalização da Beta para várias categorias:

```text
(Lula, Flávio, BN, ausência) ~ Dirichlet(alpha)
```

Use-a quando as categorias são mutuamente exclusivas e suas proporções somam
1. Ela é natural para composição, mas pode ser inadequada se as categorias
forem correlacionadas de uma forma que uma única concentração não represente.

### Normal

A Normal é útil para erros aproximadamente simétricos, sem limites rígidos:

```text
erro ~ Normal(0, sigma)
```

Não é uma boa escolha direta para probabilidades, contagens pequenas ou
variáveis que não podem ser negativas.

### Student-t

Use Student-t para erros ou mudanças contínuas quando há poucos dados ou
possibilidade de valores extremos. Seus graus de liberdade controlam as
caudas: poucos graus de liberdade produzem mais valores extremos.

Ela não deve ser escolhida apenas porque “é mais conservadora”. Verifique se
os valores extremos são plausíveis no problema e faça análise de sensibilidade.

### Poisson e binomial negativa

Poisson é um ponto de partida para contagens de eventos. Ela pressupõe que a
média e a variância são relacionadas. Se a variância observada for muito
maior que a média, a binomial negativa costuma ser mais apropriada.

## 3. O que é um prior?

Um prior representa o que o modelo considera plausível **antes de observar os
dados usados na etapa atual**. Pode vir de:

- pesquisa anterior;
- eleições anteriores;
- conhecimento de especialistas;
- restrições físicas;
- um prior deliberadamente fraco.

Em um modelo bayesiano, o posterior combina prior e verossimilhança:

```text
posterior ∝ verossimilhança × prior
```

No projeto, a etapa de zero urnas usa a Quaest como referência para gerar
cenários de coeficientes. Isso é um **prior preditivo**: ele produz previsões
antes de observar votos do segundo turno. A etapa posterior usa WLS sem esse
prior; portanto, o projeto não implementa uma atualização bayesiana integral.

### Prior não é garantia

Um prior concentrado pode dominar poucos dados. Um prior disperso permite que
os dados tenham mais influência, mas pode gerar cenários pouco plausíveis.
Sempre pergunte:

1. Qual informação justifica o centro do prior?
2. Qual informação justifica sua dispersão?
3. O que acontece se a dispersão for dobrada ou reduzida pela metade?
4. O prior gera previsões plausíveis antes de olhar os dados observados?

## 4. Como escolher a concentração da Dirichlet

Se `p` é o vetor de proporções de referência, uma parametrização comum é:

```text
alpha = k × p
```

O valor `k = soma(alpha)` é a concentração:

- `k` pequeno: cenários muito espalhados;
- `k` grande: cenários próximos de `p`.

No repositório, usa-se:

```text
alpha = 0,5 + 100 × p
```

O `100` não é automaticamente o tamanho da amostra da Quaest. É uma escolha
de dispersão. O `0,5` suaviza categorias publicadas como zero.

Uma forma melhor de justificar `k` é usar o tamanho amostral e o desenho da
pesquisa, se disponíveis, ou calibrar `k` com dados históricos. Se isso não
for possível, apresente resultados para vários valores de `k`.

## 5. Como construir um modelo

### Passo 1: definir a pergunta

Exemplos diferentes exigem modelos diferentes:

- “Qual é a média esperada?”;
- “Qual a incerteza da média?”;
- “Qual a chance de superar 50%?”;
- “Como o resultado muda quando chegam novas seções?”.

Defina também o horizonte temporal e quais dados poderiam estar disponíveis
na hora da previsão.

### Passo 2: definir a unidade de observação

Pode ser eleitor, seção, município ou estado. A unidade determina:

- quais variáveis estão disponíveis;
- quais observações são dependentes;
- qual bootstrap ou estrutura hierárquica faz sentido.

Agrupar muitas unidades pode esconder heterogeneidade. Separar demais pode
produzir estimativas instáveis.

### Passo 3: escrever o mecanismo

Antes do código, escreva uma equação. No projeto:

```text
votos previstos = origens do primeiro turno × coeficientes
```

Depois defina o que cada coeficiente significa e quais restrições ele precisa
obedecer.

### Passo 4: escolher a verossimilhança ou critério de ajuste

Para contagens, considere binomial ou multinomial. Para proporções com
denominador conhecido, considere uma verossimilhança binomial. WLS pode ser
uma aproximação útil quando se modelam respostas agregadas e pesos, mas não
substitui automaticamente um modelo probabilístico completo.

### Passo 5: incorporar conhecimento prévio

Use um prior quando existe informação anterior relevante ou quando os dados
atuais são insuficientes. Documente sua origem, escala e data. Não use o
resultado que quer prever para escolher o prior.

### Passo 6: validar

Separe validação temporal e validação por grupos. Para uma previsão eleitoral,
uma pergunta importante é:

```text
Se eu fingisse estar no início de uma eleição passada, o modelo teria
funcionado usando somente a informação disponível naquele momento?
```

Não basta reproduzir o resultado conhecido. Reprodução verifica código;
validação fora da amostra verifica capacidade de previsão.

## 6. Como comparar modelos

Compare alternativas com critérios definidos antes:

- erro absoluto ou quadrático;
- calibração das probabilidades;
- cobertura dos intervalos;
- estabilidade em eleições diferentes;
- plausibilidade substantiva;
- simplicidade e interpretabilidade.

Uma previsão que acerta o vencedor, mas fornece intervalos estreitos demais,
pode estar mal calibrada. Uma previsão com intervalo enorme pode ter boa
cobertura e pouca utilidade.

## 7. Diagnósticos importantes

### Checagem de suporte

Verifique se o modelo produz valores impossíveis:

- probabilidades negativas;
- somas diferentes de 1;
- comparecimento acima dos eleitores aptos;
- contagens negativas.

### Checagem preditiva anterior

Gere dados usando apenas o prior e pergunte se parecem plausíveis. Se o
modelo produz cenários absurdos, ajuste a estrutura antes de observar o
resultado que deseja explicar.

### Resíduos

Depois de ajustar regressão, examine resíduos por:

- tamanho da seção;
- município;
- UF;
- horário;
- composição do primeiro turno.

Padrões sistemáticos indicam que a relação linear pode estar incompleta.

### Sensibilidade

Repita a análise mudando uma decisão por vez:

- concentração da Dirichlet;
- graus de liberdade da Student-t;
- pesos;
- unidade do bootstrap;
- presença ou ausência de efeitos municipais;
- prior mais forte ou mais fraco.

Se a conclusão muda muito, essa fragilidade deve aparecer na interpretação.

## 8. Erros comuns

- confundir frequência de simulações com probabilidade objetiva;
- usar dados futuros para escolher a especificação;
- tratar um corte de apuração como amostra aleatória sem verificar;
- ignorar dependência entre seções do mesmo município;
- interpretar correlação entre origens como transferência individual;
- escolher uma distribuição somente porque ela produz um intervalo desejado;
- validar somente reproduzindo dados usados no ajuste;
- arredondar cedo demais e perder a contabilidade;
- chamar um prior informativo de “neutro” sem medir sua concentração.

## 9. Roteiro de estudo

1. Probabilidade básica: variáveis aleatórias, esperança, variância e
   quantis.
2. Distribuições: Bernoulli, binomial, Beta, Gamma, Normal, Student-t,
   multinomial e Dirichlet.
3. Regressão: mínimos quadrados, WLS, regularização e restrições.
4. Inferência: bootstrap, intervalos, calibração e validação fora da amostra.
5. Bayes: prior, verossimilhança, posterior e posterior preditivo.
6. Dados composicionais: simplex, log-ratio e modelos de composição.
7. Modelos hierárquicos: grupos, efeitos aleatórios e amostragem por
   conglomerados.

Referências acessíveis:

- [OpenIntro Statistics](https://www.openintro.org/book/os/)
- [Think Bayes, de Allen Downey](https://allendowney.github.io/ThinkBayes2/)
- [Bayesian Data Analysis, Gelman et al.](https://sites.stat.columbia.edu/gelman/book/)
- [An Introduction to Statistical Learning](https://www.statlearning.com/)
- [Stan User's Guide](https://mc-stan.org/docs/stan-users-guide/)
- [SciPy: distribuições estatísticas](https://docs.scipy.org/doc/scipy/reference/stats.html)

Para praticar, implemente primeiro um modelo simples de dois grupos, simule
dados conhecidos e tente recuperar os parâmetros. Depois acrescente uma
origem, uma distribuição Dirichlet, heterogeneidade municipal e bootstrap.
Essa sequência ajuda a distinguir o que é consequência dos dados do que é
consequência da escolha do modelo.
