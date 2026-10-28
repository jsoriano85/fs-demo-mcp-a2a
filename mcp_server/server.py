"""Event-data MCP server and the public report route."""

from __future__ import annotations

from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fsdemo.auth import (
    SCOPE_READ,
    SCOPE_WRITE,
    ScopedBearerMiddleware,
    Settings,
    Unauthorized,
    require_active_scope,
)
from fsdemo.events import (
    DiagnosisReport,
    FetchReport,
    InvalidEvents,
    RepairResult,
    diagnose_file,
    fetch_report,
    load_events,
    repair_dates,
)
from fsdemo.runtime import bootstrap, serve

UI_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


def _guard(expected: str) -> None:
    try:
        require_active_scope(expected)
    except Unauthorized as exc:
        raise ToolError(f"unauthorized for scope {exc.scope}") from exc


def build_server(settings: Settings) -> MCPServer:
    """Register the diagnose and repair tools plus GET /events."""
    csv_path = Path(settings.events_csv)
    mcp = MCPServer(
        "Event Data",
        instructions=(
            "Fetch the event report, diagnose the CSV, or repair one column: "
            "event_date, event_name, pos, listings, or seats."
        ),
    )

    @mcp.tool()
    def fetch_events() -> FetchReport:
        """Return the event report rows."""
        _guard(SCOPE_READ)
        return fetch_report(csv_path)

    @mcp.tool()
    def diagnose_events() -> DiagnosisReport:
        """Check the event CSV and report every invalid cell."""
        _guard(SCOPE_READ)
        return diagnose_file(csv_path)

    @mcp.tool()
    def repair_event_dates(
        field: str = "event_date",
        replacement: str = "",
    ) -> RepairResult:
        """Rewrite one event column into its required format."""
        _guard(SCOPE_WRITE)
        try:
            return repair_dates(csv_path, field, replacement)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.custom_route("/events", methods=["GET"])  # type: ignore[untyped-decorator]
    async def events_route(_request: Request) -> Response:
        try:
            rows = load_events(csv_path)
        except InvalidEvents as exc:
            return JSONResponse(exc.report.model_dump(), status_code=422)
        return JSONResponse([row.model_dump() for row in rows])

    return mcp


def create_app(settings: Settings | None = None) -> Starlette:
    """MCP app. /mcp requires a read or write token. /events is public."""
    current = settings or Settings.from_env()
    app = build_server(current).streamable_http_app(host=current.mcp_host)
    app.add_middleware(
        ScopedBearerMiddleware,
        tokens={
            current.read_token: SCOPE_READ,
            current.write_token: SCOPE_WRITE,
        },
        protected_prefix="/mcp",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=UI_ORIGINS,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    return app


def main() -> None:
    settings = bootstrap()
    serve(create_app(settings), settings.mcp_host, settings.mcp_port)


if __name__ == "__main__":
    main()
