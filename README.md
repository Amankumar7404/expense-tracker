# Expense Tracker (Python + Flask)

A small web app for recording daily expenses, filtering them by category, and viewing a spending summary. It started as a command-line tool and was extended with a Flask web interface that reuses the same core logic. Data is saved locally in a JSON file.

## Features

- Add expenses with an amount, category, and optional note
- Filter the expense list by category
- Summary with total spending and a percentage bar for each category
- Delete expenses (with a confirmation prompt)
- Input validation with clear error messages (bad numbers, empty category, NaN/negative amounts)
- Responsive layout that works on phones
- Templates auto-escape user input, so HTML in notes cannot inject scripts
- Command-line version still available (`tracker.py`)
- 17 automated tests with `pytest`

## Project structure

```
tracker.py        Core logic + command-line interface
app.py            Flask web app (routes only; uses tracker.py for logic)
templates/        HTML page (Jinja2)
static/           CSS
test_tracker.py   Tests for the core logic
test_app.py       Tests for the web routes
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the web app

```bash
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Run the command-line version

```bash
python tracker.py add 250 food "Lunch"
python tracker.py list
python tracker.py summary
```

## Run the tests

```bash
pytest
```

## What I learned

- Building routes, forms, and templates with Flask (including POST, redirect, and flash messages)
- Separating logic from the interface so the same code powers a CLI and a web app
- Using the application-factory pattern so tests can use a temporary data file
- Testing a web app with Flask's test client
- Basic web security: output escaping and input validation

## Ideas for future improvements

- Replace the JSON file with SQLite
- Monthly budgets with warnings
- Export to CSV
- Charts with Chart.js
- User login
- Deploy online (for example on Render or PythonAnywhere)
