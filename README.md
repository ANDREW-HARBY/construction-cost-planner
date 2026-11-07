# Construction Materials Cost Planner

**Student name:** Andrew Ashraf Harby
**Course / Assignment:** Assignment 02

## Project description
A Python application with two connected modules, joined by a menu in `main.py`:

1. **Module 1 - Material Quantity Calculator** (`module1_quantities.py`)
   A `ConcreteElement` class (ID, name, site, length, width, height, waste %) and an
   `ElementRegistry` to add, list, search and update elements. It calculates net volume,
   volume including waste, and the required cement (kg), sand (m3) and aggregate (m3)
   per element and per site, and saves them to CSV.
2. **Module 2 - Purchase and Cost Analysis** (`module2_costs.py`)
   Uses **pandas** to clean prices and purchases (missing values, duplicates, unknown IDs),
   merge the tables, and calculate costs per site, supplier and month. It compares required
   vs purchased quantities (shortage / surplus), uses **NumPy** for a price-increase scenario
   (baseline = lowest price per material), and creates four **Matplotlib** charts.

Formulas (training rates): `net = L x W x H`, `with waste = net x (1 + waste/100)`,
per m3 with waste: 300 kg cement, 0.5 m3 sand, 0.8 m3 aggregate. `cost = quantity x unit price`.
Prices have no currency in the data, so costs are shown in "currency units".

## Required libraries
`pandas`, `numpy`, `matplotlib` (and `notebook` to open the notebook). Python 3.9+.

```
pip install -r requirements.txt
```

## How to run
```
python main.py            # interactive menu
python main.py --all      # run everything without questions
python tests/run_tests.py # 3 valid + 3 invalid test cases
jupyter notebook analysis.ipynb
```

Menu: 1 add, 2 list, 3 search, 4 update, 5 quantities -> CSV, 6 clean + cost analysis -> CSV,
7 price scenario, 8 charts -> PNG, 9 run everything, 0 exit.

## Project structure
```
main.py                 menu that connects the modules
module1_quantities.py   Module 1
module2_costs.py        Module 2
analysis.ipynb          short notebook explaining the analysis
data/                   elements.csv, prices.csv, purchases.csv (sample dataset)
reports/                generated CSV reports (+ test_results.csv)
charts/                 generated PNG charts (line, bar, scatter, histogram)
tests/run_tests.py      test cases
```

## Data cleaning decisions
* Exact duplicate transactions (T009, T025) are removed.
* Rows with a missing quantity (T012, T014, T027) are removed, not guessed.
* All rejected rows and their reasons are saved in `reports/rejected_records.csv`.
* Validation: dimensions, prices and quantities > 0; waste between 0 and 100;
  duplicate IDs and unknown element/supplier references are rejected.

## Repository link
https://github.com/ANDREW-HARBY/construction-cost-planner
