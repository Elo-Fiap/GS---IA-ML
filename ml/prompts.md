# Prompts

> **1. Analise o escopo.** Leia o enunciado de ML, o escopo da solução do grupo e o problema geral da GS. Diga, critério por critério, se o escopo consegue responder ao enunciado. Se faltar algo ou se os documentos se contradisserem, aponte isso antes de começar.
>
> **2. Analise os dados antes de escolher o modelo.** Colete os dados reais e públicos citados no escopo e explore-os: o tipo do alvo, a proporção entre as classes, se há data, se há faltantes e duplicatas, quais variáveis são assimétricas e quais são categóricas. Não use dado simulado. Se uma fonte falhar, pare e me avise.
>
> **3. Escolha o modelo pelo formato do dado.** Use o que a análise mostrou:
> - se o alvo é sim/não, os dados são uma tabela e o efeito vai numa só direção (por exemplo, mais chuva, mais chance), comece pela Regressão Logística;
> - se há muitas variáveis com interações não lineares, teste XGBoost e Random Forest;
> - se for preciso uma linha de base simples, use Naive Bayes;
> - se há muito dado e relações complexas, teste uma MLP;
> - se cada exemplo é uma sequência longa em que a ordem importa, considere uma LSTM;
> - se não há rótulo, considere o KMeans.
>
> Compare os candidatos nas mesmas dobras e explique por que o escolhido ganhou. Entre modelos empatados, fique com o mais simples. Para cada modelo da lista que você descartar, diga por que ele não serve.
>
> **4. Prepare e divida os dados.** Se os dados têm data, divida pelo tempo: treine com o passado e teste com o período mais recente, sem embaralhar. Só use variáveis que já existem no momento em que a decisão é tomada. Se as classes forem desbalanceadas, não avalie pela acurácia e não crie dados sintéticos. Deixe o pré-processamento dentro de um `Pipeline`, para nada do teste vazar para o treino.
>
> **5. Faça a hiperparametrização para validar o modelo.** Teste ao menos 10 combinações de 3 hiperparâmetros, com validação cruzada só no treino. Se os dados têm data, a validação cruzada também respeita o tempo. Escolha os hiperparâmetros pelo que a análise mostrou: regularização se houver muitas variáveis, peso de classe se houver desbalanceamento, profundidade e número de árvores se o modelo for de árvore. Mostre o desempenho no treino e na validação de cada combinação. Se a melhor ficar na borda da grade, amplie a grade.
>
> **6. Descubra por quanto tempo o modelo aguenta sem ser treinado de novo.** Não treine com todas as amostras. Deixe o período mais recente fora do treino e meça o desempenho mês a mês depois do fim do treino. Repita com o treino terminando em datas diferentes, para ver em quanto tempo a métrica começa a cair. Com isso, diga de quanto em quanto tempo o modelo precisa ser treinado de novo.
>
> **7. Mostre os resultados.** Coloque as métricas de treino e teste lado a lado, com gráficos, e compare com linhas de base simples, como o acaso e uma regra óbvia. Discuta o overfitting e conclua o que o resultado significa para o cidadão.
>
> **8. Revise com subagentes.** Coloque um subagente para reavaliar o código, procurando bugs e vazamento de dados e rodando tudo do zero. Coloque outro para avaliar se o trabalho está condizente com o que o enunciado pede.
>
> **9. Corrija como um professor rígido.** Ao final, coloque um subagente para agir como um professor rígido e dar uma nota de 0 a 10, usando os critérios do enunciado. Se a nota não for 10, ele deve apontar onde o trabalho não chegou ao 10 e por quê.
>
> **10. Refaça até chegar a 10.** Corrija o que o professor apontou e peça uma nova correção ao subagente, até a nota chegar a 10.
>
> Pode usar subagentes para cada parte, dividindo o trabalho em tarefas.
