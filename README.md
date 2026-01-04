# Autheur

GUEBOUL ILYES / FRANCOIS LIU

# IMMOBILIER

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

L’objectif de ce projet est de prédire le prix de vente de maisons et d’appartements à partir de leurs caractéristiques (ville, type de bien, surface, nombre de pièces, nombre de chambres, nombre de salles de bain, DPE, etc.). Les données proviennent du site d’annonces immobilières entre particuliers immo-entre-particuliers.com. Le projet met en œuvre une chaîne complète de traitement allant de la collecte automatique des données par web scraping jusqu’à la modélisation en apprentissage automatique avec PySpark.

Dans une première étape, réalisée en Python, nous développons un module de web scraping basé sur les bibliothèques requests et BeautifulSoup. Pour chaque annonce, nous extrayons le prix, la ville, le type de bien, la surface habitable, le nombre de pièces, de chambres, de salles de bain ainsi que la classe énergétique (DPE). Nous appliquons des filtres pour ne conserver que les annonces pertinentes (uniquement maisons et appartements, prix supérieurs à 10 000 €, informations essentielles présentes et cohérentes). Les données nettoyées sont ensuite enregistrées dans un fichier au format CSV ou Parquet, qui sert de base au traitement Big Data.


## Datasets

Ce projet repose sur deux jeux de données distincts, correspondant à différentes étapes du pipeline de traitement des données.

idf_ventes.csv est un jeu de données brut issu du scraping d’annonces immobilières en Île-de-France.
cities.csv est un eu de données de référence contenant des informations géographiques sur les villes françaises téléchargé depuis le site https://www.data.gouv.fr/datasets/villes-de-france. 

Les deux fichiers CSV sont combinés lors de la phase de nettoyage afin de produire un dataset enrichi.


## Project Organization

```
├── LICENSE            <- Open-source license if one is chosen
├── Makefile           <- Makefile with convenience commands like `make data` or `make train`
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.
│
├── docs               <- A default mkdocs project; see www.mkdocs.org for details
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering),
│                         the creator's initials, and a short `-` delimited description, e.g.
│                         `1.0-jqp-initial-data-exploration`.
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         IMMOBILIER and configuration for tools like black
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
├── requirements.txt   <- The requirements file for reproducing the analysis environment, e.g.
│                         generated with `pip freeze > requirements.txt`
│
├── setup.cfg          <- Configuration file for flake8
│
└── IMMOBILIER   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes IMMOBILIER a Python module
    │
    ├── config.py               <- Store useful variables and configuration
    │
    ├── dataset.py              <- Scripts to download or generate data
    │
    ├── features.py             <- Code to create features for modeling
    │
    ├── modeling                
    │   ├── __init__.py 
    │   ├── predict.py          <- Code to run model inference with trained models          
    │   └── train.py            <- Code to train models
    │
    └── plots.py                <- Code to create visualizations
```

--------

# Github

https://github.com/liufrancois/IMMOBILIER
