"""Build the presenter PDF for the MCP and A2A demo."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import Color, black
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

PAGE_WIDTH, PAGE_HEIGHT = A4
FILL = Color(0.93, 0.95, 0.97)
REJECT = Color(0.96, 0.90, 0.90)
ALLOW = Color(0.90, 0.95, 0.90)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "GuideTitle",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=22,
            leading=26,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=12,
            leading=16,
            textColor=Color(0.2, 0.2, 0.2),
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "GuideH1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "GuideH2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "GuideBody",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10.5,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "GuideBullet",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10.5,
            leading=14,
            leftIndent=14,
            bulletIndent=2,
            spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "GuideCode",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8,
            leading=11,
            leftIndent=6,
            rightIndent=6,
            spaceBefore=4,
            spaceAfter=8,
            backColor=Color(0.95, 0.95, 0.95),
        ),
    }
    return styles


def _text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def _body(styles: dict[str, ParagraphStyle], value: str) -> Paragraph:
    return Paragraph(_text(value), styles["body"])


def _bullet(styles: dict[str, ParagraphStyle], value: str) -> Paragraph:
    return Paragraph(f"• {_text(value)}", styles["bullet"])


def _code(styles: dict[str, ParagraphStyle], value: str) -> Paragraph:
    return Paragraph(_text(value), styles["code"])


class Diagram(Flowable):
    """A flowchart drawn directly on the page."""

    def __init__(
        self,
        width: float,
        height: float,
        painter: Callable[[object, float, float], None],
    ) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._painter = painter

    def wrap(
        self, available_width: float, available_height: float
    ) -> tuple[float, float]:
        return self._width, self._height

    def draw(self) -> None:
        self._painter(self.canv, self._width, self._height)


def _box(
    canvas: object, x: float, y: float, w: float, h: float, text: str, fill: Color
) -> None:
    canvas.setStrokeColor(black)  # type: ignore[attr-defined]
    canvas.setFillColor(fill)  # type: ignore[attr-defined]
    canvas.roundRect(x, y, w, h, 4, fill=1, stroke=1)  # type: ignore[attr-defined]
    canvas.setFillColor(black)  # type: ignore[attr-defined]
    canvas.setFont("Helvetica", 8)  # type: ignore[attr-defined]
    lines = text.split("\n")
    top = y + (h + (len(lines) * 10)) / 2 - 8
    for index, line in enumerate(lines):
        canvas.drawCentredString(x + w / 2, top - index * 10, line)  # type: ignore[attr-defined]


def _arrow(canvas: object, x1: float, y1: float, x2: float, y2: float) -> None:
    canvas.setStrokeColor(black)  # type: ignore[attr-defined]
    canvas.setFillColor(black)  # type: ignore[attr-defined]
    canvas.line(x1, y1, x2, y2)  # type: ignore[attr-defined]
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 >= x1 else -1
        tip_x = x2
        tip_y = y2
        canvas.line(tip_x, tip_y, tip_x - 6 * direction, tip_y + 3)  # type: ignore[attr-defined]
        canvas.line(tip_x, tip_y, tip_x - 6 * direction, tip_y - 3)  # type: ignore[attr-defined]
    else:
        direction = 1 if y2 >= y1 else -1
        canvas.line(x2, y2, x2 - 3, y2 - 6 * direction)  # type: ignore[attr-defined]
        canvas.line(x2, y2, x2 + 3, y2 - 6 * direction)  # type: ignore[attr-defined]


def _label(canvas: object, x: float, y: float, text: str) -> None:
    canvas.setFillColor(black)  # type: ignore[attr-defined]
    canvas.setFont("Helvetica", 7)  # type: ignore[attr-defined]
    canvas.drawCentredString(x, y, text)  # type: ignore[attr-defined]


def _paint_architecture(canvas: object, width: float, height: float) -> None:
    _box(canvas, 16, 178, 100, 40, "Terminal UI\n:5173", FILL)
    _box(canvas, 150, 178, 130, 40, "Coordinator\n:8001", FILL)
    _box(canvas, 360, 178, 104, 40, "Ollama\nllama3.2", FILL)
    _box(canvas, 16, 96, 110, 40, "Fetch\n:8004", FILL)
    _box(canvas, 175, 96, 130, 40, "Diagnosis\n:8002", FILL)
    _box(canvas, 354, 96, 110, 40, "Repair\n:8003", FILL)
    _box(canvas, 175, 16, 130, 40, "MCP server\n:8000", FILL)
    _box(canvas, 354, 20, 110, 32, "events.csv", FILL)
    _arrow(canvas, 116, 198, 150, 198)
    _label(canvas, 133, 204, "POST /chat")
    _arrow(canvas, 280, 198, 360, 198)
    _label(canvas, 320, 204, "choose card")
    _arrow(canvas, 180, 178, 71, 136)
    _arrow(canvas, 215, 178, 240, 136)
    _label(canvas, 250, 156, "A2A")
    _arrow(canvas, 250, 178, 409, 136)
    _arrow(canvas, 71, 96, 190, 56)
    _arrow(canvas, 240, 96, 240, 56)
    _label(canvas, 268, 74, "MCP")
    _arrow(canvas, 409, 96, 290, 56)
    _arrow(canvas, 305, 36, 354, 36)


def _paint_sequence(canvas: object, width: float, height: float) -> None:
    steps = [
        "1  The page opens with No report loaded. Focus stays in the terminal.",
        "2  Load the report. The model selects the Fetch Agent card.",
        "3  Fetch calls fetch_events and the table shows nine rows.",
        "4  Corrupt a date, then ask the terminal to refresh the report.",
        "5  The table says Cannot load the report and hides the bad cell.",
        "6  Ask why it failed. Diagnosis prints the Error line for that cell.",
        "7  Repair rewrites a parseable date, or the valid date you name.",
        "8  Refresh the report. The table shows the repaired value.",
    ]
    box_h = 16
    gap = 5
    top = height - 8
    for index, step in enumerate(steps):
        y = top - (index + 1) * (box_h + gap)
        _box(canvas, 8, y, width - 16, box_h, step, FILL)
        if index:
            previous = y + box_h + gap
            _arrow(canvas, 24, previous, 24, y + box_h)


def _paint_auth(canvas: object, width: float, height: float) -> None:
    _box(canvas, 12, 168, 150, 36, "Fetch, diagnosis\ntools:events:read", ALLOW)
    _box(canvas, 190, 168, 150, 36, "fetch_events\ndiagnose_events", ALLOW)
    _box(canvas, 368, 168, 130, 36, "repair tool\nrejected", REJECT)
    _box(canvas, 12, 96, 150, 36, "Repair agent\ntools:events:write", ALLOW)
    _box(canvas, 190, 96, 150, 36, "repair_event_dates\nfive columns", ALLOW)
    _box(canvas, 368, 96, 130, 36, "unknown field\nrejected", REJECT)
    _box(canvas, 12, 24, 150, 36, "Coordinator\nagent:delegate", FILL)
    _box(canvas, 190, 24, 150, 36, "A2A /a2a\nallowed", ALLOW)
    _box(canvas, 368, 24, 130, 36, "wrong bearer\nHTTP 401", REJECT)
    _arrow(canvas, 162, 186, 190, 186)
    _arrow(canvas, 340, 186, 368, 186)
    _arrow(canvas, 162, 114, 190, 114)
    _arrow(canvas, 340, 114, 368, 114)
    _arrow(canvas, 162, 42, 190, 42)
    _arrow(canvas, 340, 42, 368, 42)


def _footer(canvas: object, doc: object) -> None:
    canvas.saveState()  # type: ignore[attr-defined]
    canvas.setFont("Times-Roman", 8)  # type: ignore[attr-defined]
    canvas.setFillColor(black)  # type: ignore[attr-defined]
    canvas.drawString(18 * mm, 12 * mm, "MCP and A2A: Connecting AI Systems")  # type: ignore[attr-defined]
    canvas.drawRightString(  # type: ignore[attr-defined]
        PAGE_WIDTH - 18 * mm,
        12 * mm,
        str(doc.page),  # type: ignore[attr-defined]
    )
    canvas.restoreState()  # type: ignore[attr-defined]


def build(path: Path) -> None:
    """Write the presenter guide to ``path``."""
    styles = _styles()
    story: list[object] = [
        Paragraph("MCP and A2A: Connecting AI Systems", styles["title"]),
        _body(
            styles,
            "Read the lines that start with Say. Do the lines that start "
            "with Show. The story takes about 15 to 20 minutes.",
        ),
        Paragraph("MCP means Model Context Protocol", styles["h1"]),
        _body(
            styles,
            "Say: MCP is a standard way for an AI application to use a tool "
            "or a data source that lives outside itself. A server publishes "
            "tools. Each tool has a name, inputs, and a result. A client "
            "lists the tools and calls the one it needs. The client does not "
            "need the server's private files. It only needs the tool's name "
            "and contract. MCP is the link from an agent to a tool.",
        ),
        Paragraph("A2A means Agent to Agent", styles["h1"]),
        _body(
            styles,
            "Say: A2A is a standard way for one agent to ask another agent "
            "to do work. Each agent publishes an Agent Card. The card gives "
            "the agent's name, the jobs it offers, and the address where a "
            "task can be sent. Those jobs are called skills. A skill is the "
            "advertisement on the card. It is not the tool that does the "
            "work. Another agent reads the card, sends one task, and waits "
            "for a result. A2A is the link from an agent to an agent.",
        ),
        Paragraph("Authentication", styles["h1"]),
        _body(
            styles,
            "Say: A call that does real work carries a bearer token in the "
            "Authorization header. The token is a shared secret that says "
            "who is calling. Each token is limited to one permission, called "
            "a scope. A real token with the wrong scope is still refused. A "
            "missing or wrong token is rejected before any work starts. "
            "Describing a service, such as publishing an Agent Card, can "
            "stay public. Using the service cannot. In production, replace "
            "shared tokens with a login system such as OAuth or mutual TLS. "
            "The rule stays the same: give each caller only the permission "
            "that job needs.",
        ),
        Paragraph("The problem", styles["h1"]),
        _body(
            styles,
            "Say: A single screen that loads data and also fixes it hides "
            "who did the work, and it gives that screen permission to change "
            "the file. A person cannot tell a read from a repair. A bad "
            "value and the explanation of that value get mixed together. We "
            "want a person to ask in ordinary words. We want one front desk "
            "to choose a specialist. We want only that specialist to touch "
            "the data, and only with the permission its job needs.",
        ),
        _body(
            styles,
            "Say: This demo splits that work. The page never opens the file. "
            "Every sentence goes to a coordinator. A model reads the "
            "specialists' cards and picks one. One specialist loads the "
            "rows and, when the file is bad, says only that it cannot load "
            "them. Another specialist names the bad cell. A third changes "
            "one column. The file itself is opened by one tool server, and "
            "that server checks the caller's permission first.",
        ),
        Paragraph("The projects", styles["h1"]),
        Paragraph("mcp_server", styles["h2"]),
        _body(
            styles,
            "Say: mcp_server is the tool server. In a real system it would "
            "not open the datasource itself. It would call an API that owns "
            "the data. For this demo, the MCP server is allowed to connect "
            "straight to the datasource, the file data/events.csv. Its tools "
            "are the functions in mcp_server/server.py. fetch_events reads "
            "the rows. If the datasource is bad, it says only Cannot load "
            "the report. diagnose_events names the bad cell: the row, the "
            "column, the value, and the expected shape. repair_event_dates "
            "fixes one column: the date, the name, the seller, the listing "
            "count, or the seat count. A date it understands becomes "
            "10-21-2026 17:30. An impossible date stays until the request "
            "names a real one. It writes a temporary file, then replaces "
            "the datasource. It listens at http://127.0.0.1:8000/mcp.",
        ),
        _bullet(styles, "Show: mcp_server/server.py, the three tool functions."),
        Paragraph("coordinator_agent", styles["h2"]),
        _body(
            styles,
            "Say: coordinator_agent is the front desk. It does not open the "
            "datasource and it does not hunt for special words. Its skill "
            "is written in coordinator_agent/agent.py, in the function "
            "coordinator_card, in the list called skills. The skill id is "
            "coordinate_event_report. The name is Coordinate event report. "
            "It means: choose fetch, diagnosis, or repair. The live card is "
            "at http://127.0.0.1:8001/.well-known/agent-card.json. The "
            "coordinator reads the other cards and asks a local model which "
            "one fits the sentence. For a repair, the model also names the "
            "column. Then it sends that one request to the chosen agent.",
        ),
        Paragraph("fetch_agent", styles["h2"]),
        _body(
            styles,
            "Say: fetch_agent loads or refreshes the report. Its skill is "
            "in fetch_agent/agent.py, function fetch_card. The skill id is "
            "fetch_events. The name is Fetch events. It calls the MCP read "
            "tool of the same name. It does not explain a bad cell. It runs "
            "on port 8004. Its card is "
            "http://127.0.0.1:8004/.well-known/agent-card.json.",
        ),
        Paragraph("diagnosis_agent", styles["h2"]),
        _body(
            styles,
            "Say: diagnosis_agent finds what is wrong. Its skill is in "
            "diagnosis_agent/agent.py, function diagnosis_card. The skill id "
            "is diagnose_events. The name is Diagnose events. It calls the "
            "MCP read tool of the same name and returns the bad cell. It "
            "does not change the file. It runs on port 8002.",
        ),
        Paragraph("repair_agent", styles["h2"]),
        _body(
            styles,
            "Say: repair_agent is the only agent that may change the file. "
            "Its skill is in repair_agent/agent.py, function repair_card. "
            "The skill id is repair_event_dates. The name is Repair event "
            "dates. It calls the MCP write tool and rewrites one column. It "
            "runs on port 8003.",
        ),
        Paragraph("Report UI", styles["h2"]),
        _body(
            styles,
            "Say: The report UI is the window a person sees. The project is "
            "the ui folder. It starts with the words No report loaded, and "
            "the cursor stays in the terminal. There is no command menu. "
            "Every sentence goes to the coordinator. The page does not call "
            "MCP, it does not call the other agents, and it does not open "
            "the datasource. It runs at http://127.0.0.1:5173.",
        ),
        _bullet(styles, "Show: the empty panel, then the terminal."),
        Paragraph("How the pieces fit", styles["h1"]),
        _body(
            styles,
            "Say: The page talks only to the coordinator, over ordinary web "
            "requests. The coordinator talks to one helper, using A2A. That "
            "helper talks to a tool, using MCP. The model only chooses the "
            "card. Fetch and Diagnosis may only read. Repair may only write.",
        ),
        Diagram(480, 230, _paint_architecture),
        Spacer(1, 6),
        Paragraph("Who is allowed to do what", styles["h1"]),
        _body(
            styles,
            "Say: Reading a card is public. Calling a tool is not. The read "
            "pass is named tools:events:read. It may fetch or diagnose. The "
            "write pass is named tools:events:write. It may repair one of "
            "the five columns. The coordinator's pass is named "
            "agent:delegate. It may hand work to a helper, and nothing else. "
            "The page never receives the write pass. If Fetch or Diagnosis "
            "tries to repair, the tool says no. A missing or wrong pass "
            "stops the call before any work starts. In a real system, "
            "replace these shared demo passes with a login system such as "
            "OAuth, and keep the same three permissions.",
        ),
        Diagram(480, 240, _paint_auth),
        Spacer(1, 6),
        Paragraph("Live demo", styles["h1"]),
        _body(
            styles,
            "Say: I will leave the page empty, then ask for the report in "
            "plain words. After I break one date, a refresh will not tell "
            "us which cell is wrong. I have to ask. After the repair, the "
            "table does not update by itself. I have to ask for a refresh.",
        ),
        Diagram(480, 200, _paint_sequence),
        Spacer(1, 6),
        Paragraph("What to point at", styles["h2"]),
        _bullet(styles, "Show: No report loaded, with the cursor still in the terminal."),
        _bullet(
            styles,
            "Show: the Fetch card at http://127.0.0.1:8004/.well-known/agent-card.json and the skill fetch_events.",
        ),
        _bullet(styles, "Show: Cannot load the report, with no row number and no bad value."),
        _bullet(
            styles,
            "Show: the Diagnosis card, then the line Error: Row 1, event_date = 10/21/26 17:30. Expected MM-dd-yyyy HH:mm.",
        ),
        _bullet(
            styles,
            "Show: the Repair card. A date such as 10/21/26 17:30 can be fixed without a replacement. An impossible date such as 13-25-2026 13:30 changes only when the sentence names a real date.",
        ),
        _bullet(styles, "Show: the refreshed table. The fixed date uses 10-21-2026 17:30."),
        Paragraph("Close", styles["h2"]),
        _body(
            styles,
            "Say: The page only knows the front desk. The model only picks a "
            "card. MCP is how a helper touches the file. The pass is what "
            "stops a reader from becoming an editor.",
        ),
        Paragraph("Before the room arrives", styles["h1"]),
        _body(
            styles,
            "Do this once, from the project folder, in PowerShell. You need "
            "Python 3.12 and Node 20.",
        ),
        _code(
            styles,
            "python -m venv .venv\n"
            '.\\.venv\\Scripts\\python -m pip install -e ".[dev]"\n'
            "Copy-Item sample.env .env\n"
            "cd ui\n"
            "corepack enable\n"
            "corepack prepare pnpm@9.15.9 --activate\n"
            "pnpm install\n"
            "cd ..",
        ),
        _body(
            styles,
            "Install Ollama once and pull llama3.2 once. Put the next three "
            "lines in .env. The key can be any non-empty string. Ollama does "
            "not check it.",
        ),
        _code(
            styles,
            "winget install --id Ollama.Ollama -e\n"
            "ollama pull llama3.2",
        ),
        _code(
            styles,
            "LLM_BASE_URL=http://127.0.0.1:11434/v1\n"
            "LLM_MODEL=llama3.2\n"
            "LLM_API_KEY=ollama",
        ),
        _body(styles, "Start every server with one command:"),
        _code(styles, ".\\start-demo.cmd"),
        _body(
            styles,
            "Open http://127.0.0.1:5173. The report stays empty until the "
            "terminal asks for it. Corrupt and restore from another terminal:",
        ),
        _code(
            styles,
            ".\\.venv\\Scripts\\python data\\corrupt_event_date.py\n"
            ".\\.venv\\Scripts\\python data\\restore_events.py",
        ),
        Paragraph("Lines to type", styles["h1"]),
        _body(
            styles,
            "Type these, or a sentence close to them. The model chooses the "
            "helper. The terminal will not offer them as buttons.",
        ),
        _code(styles, "Load the report"),
        _body(
            styles,
            "You should see Fetch Agent, then Loaded 9 events, and the nine "
            "show times. Refresh the report asks Fetch again.",
        ),
        _code(styles, "Why did the report fail?"),
        _body(
            styles,
            "After a broken refresh, you should see Diagnosis Agent, then "
            "Error: Row 1, event_date = \"10/21/26 17:30\". Expected "
            "MM-dd-yyyy HH:mm.",
        ),
        _code(styles, "Repair the event_date value to 10-21-2026 17:30"),
        _body(
            styles,
            "You should see Repair Agent and one row rewritten. Ask to "
            "refresh before the table changes. A date such as 10/21/26 17:30 "
            "can be fixed without naming the new value. An impossible date "
            "such as 13-25-2026 13:30 stays until the sentence names a real "
            "date. Repairing a file that is already correct changes zero rows.",
        ),
        Paragraph("If a port is busy", styles["h1"]),
        _body(
            styles,
            "Free ports 8000, 8001, 8002, 8003, 8004, and 5173. Ollama listens "
            "on 11434. If the live processes cannot start, run the tests and "
            "walk the same assertions:",
        ),
        _code(styles, ".\\.venv\\Scripts\\python -m pytest"),
        _body(
            styles,
            "tests/test_events.py checks the bad date, a named replacement "
            "for an impossible date, and the refusal to edit an unknown "
            "field. tests/test_report_api.py checks HTTP 200, HTTP 422, and "
            "the wrong token. tests/test_stack.py starts a stand-in model "
            "and the fetch, diagnosis, and repair agents, then checks load, "
            "refresh, diagnosis, repair, and HTTP 401.",
        ),
    ]
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="MCP and A2A: Connecting AI Systems",
        author="FS Demo",
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)


def main() -> None:
    output = Path(__file__).with_name("mcp-a2a-demo-guide.pdf")
    build(output)


if __name__ == "__main__":
    main()
