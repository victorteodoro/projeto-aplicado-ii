# Projeto Aplicado 2 - Classificação de áreas desmatadas
Aqui Datasets, análises e resultados da disciplina Projeto Integrado II do curso de Ciência de Dados do Mackenzie

## Membros

| Nome                         | RA       | Email                       |
| ---------------------------- | -------- | --------------------------- |
| Rafael Vidal de Tomy         | 10414804 | 10414804@mackenzista.com.br |
| Victor José de Souza Teodoro | 10414609 | 10414609@mackenzista.com.br |

## Introdução
São Tomé das Letras, em Minas Gerais, que viu o turismo crescer no fim do século 20 como uma nova fonte de renda, ainda tem sua cultura enraizada na mentalidade mineradora. Um modus operandi que consiste em "minerar" os recursos naturais até que o fim venha pela completa escassez.

Em força contrária a degradação contínua do meio ambiente equilibrado, munícipes se uniram em um movimento orgânico em 2015. Essa união se consolidou no Movimento Todos Pela Água, com atuação ampla. Então, com a necessidade de formalização do movimento para ampliar sua área e poder de atuação, surgiu em 21 de setembro de 2023 a [Associação Socioambiental Água é Vida – ASAV](https://asav.com.br/).

Com a alta disponibilidade de imagens de satélite atualmente, propomos criar um classificador de imagens para detectar áreas em desacordo com a legislação ambiental.

## Organização do repositório
O repositório possui duas pastas fundamentais:

- [Models](./models): em que guardamos os modelos treinados para serem reutilizados.
- [Notebooks](./notebooks): em que guardamos os notebooks Jupyter utilizados.
- [Helpers](./helpers): classes e funções de ajuda na análise e limpeza dos dados.

## Reproduzindo os resultados
Para reproduzir localmente, clone o repositório, vá até a pasta em que clonou e:

1. Clone o repositório 👇

```bash
git clone https://github.com/FelipeAvelart/projeto_integradormackenzie.git
```
2. Vá até a pasta do repositório 👇

```bash
cd projeto_integradormackenzie
```

3. [Instale o `miniconda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)

4. Instale as dependências do projeto 👇

```bash
conda env create -f environment.yml
```

5. Ative o ambiente 👇

```bash
conda activate proj-carcara
```

6. Rode o jupyter lab 👇

```bash
jupyter lab
```
## Sumário
1. [Teste prático de aquisição de dados](https://github.com/victorteodoro/projeto-aplicado-ii/blob/main/1_Teste_pr%C3%A1tico_de_aquisi%C3%A7%C3%A3o_de_dados.ipynb)
2. [Aquisição de dados para o projeto](https://github.com/victorteodoro/projeto-aplicado-ii/blob/main/2_Aquisi%C3%A7%C3%A3o_de_dados_para_o_projeto.ipynb)
3. [Preparação dos dados: rotulação dos pixeis](https://github.com/victorteodoro/projeto-aplicado-ii/blob/main/3_Prepara%C3%A7%C3%A3o_dos_dados_rotula%C3%A7%C3%A3o_dos_pixeis.ipynb)
4. [Preparando o conjunto de treinamento](https://github.com/victorteodoro/projeto-aplicado-ii/blob/main/4_Preparando_o_conjunto_de_treinamento.ipynb)
5. [Treinando e testando o modelo](https://github.com/victorteodoro/projeto-aplicado-ii/blob/main/5_Treinando_e_testando_o_modelo.ipynb)
