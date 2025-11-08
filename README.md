Step 1: Install UV
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Clone Repository
```
bash
git clone <repo-url>
cd VocalOS-Be
```
2. Create Virtual Environment
```
bash
uv venv
```
3. Activate Virtual Environment

macOS/Linux:
```
bash
source .venv/bin/activate
```
Windows:
```
bash
.venv\Scripts\activate
```

4. Sync Dependencies
```
bash
uv sync
```
5. Run

```
bash
uv run python src/main.py
```
