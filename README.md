# Data Engineering Projects

This repository holds the data engineering projects I build as I learn. Each project takes messy or scattered input and produces a clean file that someone can analyse. Every project lives in its own folder with its own README.

## Projects

### Day 1: Duka Connect customer extraction

[day1-api-extraction](day1-api-extraction)

A Nairobi distributor needs customer records from a partner API in a flat format. `extract_customers.py` calls the API with `requests`, checks the HTTP response and the JSON payload, keeps the fields needed for analysis, flattens the nested JSON with `pandas`, and writes `output/customers_clean.csv`. The distributor can join that file with its internal data.

### Day 2: Soko Fresh daily till export

[day2-multi-file-pipeline](day2-multi-file-pipeline)

Soko Fresh has branches in Nairobi, Mombasa, Kisumu and Nakuru. Each branch exports a `transactions_*.csv` file from its till every day. `pipeline.py` reads all of them and writes a consolidated CSV of valid rows, a separate CSV of rejected rows, and a summary of the run. It uses only the Python standard library, so there is nothing to install.

## Repository layout

```
data-engineering-projects/
├── README.md
├── day1-api-extraction/
│   ├── README.md
│   ├── extract_customers.py
│   ├── requirements.txt
│   └── output/
│       └── customers_clean.csv
└── day2-multi-file-pipeline/
    ├── README.md
    └── pipeline.py
```

## Running a project

Open the project folder and follow its README. Day 1 needs the packages in its `requirements.txt`. Day 2 needs only Python 3.

## Roadmap

Later projects will cover:

- SQL and warehouse workflows
- Data modeling
- Reporting and visualization
- Workflow automation and scheduling