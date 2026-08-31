# Desafio Técnico - Assistente de BI

## Objetivo
Consolidar as bases de Associados, Produtos e Movimentação, criar indicadores de relacionamento, classificar os associados e disponibilizar os dados tratados para
um dashboard executivo no Power BI.

## Tecnologias utilizadas
- Python (pandas, openpyxl) — tratamento e consolidação dos dados
- Excel — fonte de dados bruta e conferência
- Power BI Desktop — modelagem e dashboard
- Git — versionamento


## Tratamento de dados (src/etl.py)
- Duplicados: remoção por CHAVE (identificador único) e por linha completa.
- Nulos: `RENDA_MENSAL` nulo é imputado pela mediana (métrica robusta a outliers); métricas de movimentação nulas são tratadas como 0.
- Padronização de texto: nomes em title case; cidades normalizadas (ex.:"P. Branco", "PATO BRANCO" e "Pato Branco" → um único valor); agência padronizada como código de 2 dígitos.
- Datas inconsistentes: datas de associação futuras (erro de carga) são tratadas como ausentes.
- Consolidação: as três bases são unidas pela chave `CHAVE`.

## Indicadores criados
- Quantidade de Produtos: total de produtos com contratação "Sim" por associado.
- Tempo de Relacionamento (anos): data atual - data de associação.
- Faixa de Renda: Até R$3.000 / R$3.001–R$8.000 / R$8.001–R$15.000 / Acima de R$15.000.
- Score de Uso: média normalizada de saldo médio, PIX mensal e compras no cartão — usado para medir intensidade de uso dos serviços.

## Regras de classificação
| Classe | Critério |
| Engajado | Score de uso no top 25% e 4+ produtos |
| Maduro | 4+ produtos e mais de 3 anos de relacionamento **e** saldo médio acima da mediana |
| Inicial | Até 1 produto **e** menos de 2 anos de relacionamento |
| Em Desenvolvimento | Demais casos (2–3 produtos, relacionamento em crescimento, uso moderado) |

A metodologia prioriza intensidade de uso e diversificação de produtos como sinais mais fortes de engajamento do que apenas o tempo de casa.

## Modelo Power BI
Tabelas conectadas no modelo (Power BI Desktop):
- `Associados` — dados cadastrais
- `Produtos` — produtos contratados
- `Movimentacao` — indicadores financeiros
- Relacionamentos 1:1 entre as três tabelas pela `CHAVE`
- Medidas DAX para os KPIs executivos (Total de Associados, Renda Média, Saldo Médio, Produtos por Associado, distribuição por classificação)

## Passo a passo para execução
1. Instale as dependências: `pip install pandas openpyxl`
2. Rode o ETL: `python src/etl.py`
3. Os arquivos tratados serão gerados em `data/processed/`
4. Abra o Power BI Desktop e importe `data/processed/base_consolidada.xlsx` (ou use o modelo já publicado no `.pbix` do repositório)
5. As páginas do dashboard usam as medidas e colunas descritas acima

## Dashboard (páginas)
1. Visão Geral — Total de Associados, Renda Média, Saldo Médio, Produtos por Associado
2. Relacionamento — Associados por Agência/Cidade, Faixa de Renda, Tempo de Relacionamento
3. Classificação — participação percentual e quantitativa por classe
4. Oportunidades — associados de alta renda com poucos produtos, baixa utilização, e potencial de crescimento
