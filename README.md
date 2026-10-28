# MCP and A2A events demo

The browser talks only to the coordinator. A model reads the fetch, diagnosis, and repair Agent Cards and picks one. Those agents call MCP. The report stays empty until the terminal asks for it.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item sample.env .env
cd ui
corepack enable
corepack prepare pnpm@9.15.9 --activate
pnpm install
cd ..
```

Start every server from the repository root with one command:

```powershell
.\start-demo.cmd
```

Or start each process in its own terminal:

```powershell
.\.venv\Scripts\python -m mcp_server
.\.venv\Scripts\python -m coordinator_agent
.\.venv\Scripts\python -m diagnosis_agent
.\.venv\Scripts\python -m repair_agent
.\.venv\Scripts\python -m fetch_agent
pnpm --dir ui dev
```

Put an API key in `.env` as `LLM_API_KEY`. Open `http://127.0.0.1:5173` and ask the terminal to load, refresh, investigate, or repair the report. Corrupt and restore the CSV from another terminal:

```powershell
.\.venv\Scripts\python data\corrupt_event_date.py
.\.venv\Scripts\python data\restore_events.py
```

## Test

```powershell
.\.venv\Scripts\python -m pytest
```

## Presenter PDF

```powershell
.\.venv\Scripts\python -m docs.build_guide
```

The guide is written to `docs/mcp-a2a-demo-guide.pdf`.

## Make targets

`make format`, `make lint`, `make test`, `make docs`.
