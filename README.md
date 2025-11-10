# Audeint

## Presntation Deck
[View Canva Design](https://www.canva.com/design/DAG4PUl6rAg/CTvamOW3CWJurWlOB47LCw/view?utm_content=DAG4PUl6rAg&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h2bf6e7ecbb)





## For Developers

Step 1: Install UV
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Clone Repository
```
git clone <repo-url>
cd VocalOS-Be
```

2. Create Virtual Environment
```
uv venv
```

3. Activate Virtual Environment

macOS/Linux:
```
source .venv/bin/activate
```

Windows:
```
.venv\Scripts\activate
```

4. Sync Dependencies
```
uv sync
```

5. Run
```
uv run python src/main.py
```

