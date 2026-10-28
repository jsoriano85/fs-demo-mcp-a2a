import { useEffect, useRef, useState } from "react";

const COORDINATOR_URL =
  import.meta.env.VITE_COORDINATOR_URL ?? "http://127.0.0.1:8001";

type EventRow = {
  event_date: string;
  event_name: string;
  pos: string;
  listings: number;
  seats: number;
};

type DataIssue = {
  row: number;
  field: string;
  value: string;
  expected_format: string;
};

type ChatArtifact = {
  ok?: boolean;
  message?: string;
  rows?: EventRow[];
  issues?: DataIssue[];
  rows_changed?: number;
  field?: string;
  format?: string;
  unparsed?: DataIssue[];
};

type ChatReply = {
  specialist: string;
  artifact: ChatArtifact;
};

type Turn = {
  id: number;
  role: "user" | "agent";
  text: string;
};

function issueLine(issue: DataIssue): string {
  return `Error: Row ${issue.row}, ${issue.field} = "${issue.value}". Expected ${issue.expected_format}.`;
}

function describe(reply: ChatReply): string {
  const issues = reply.artifact.issues ?? [];
  if (issues.length > 0) {
    return issues.map(issueLine).join("\n");
  }
  if (reply.artifact.ok === false) {
    return reply.artifact.message || "Cannot load the report";
  }
  if (Array.isArray(reply.artifact.rows)) {
    return reply.artifact.message || `Loaded ${reply.artifact.rows.length} events.`;
  }
  const lines: string[] = [];
  if (typeof reply.artifact.rows_changed === "number") {
    lines.push(
      `Repaired ${reply.artifact.field}: ${reply.artifact.rows_changed} row(s) rewritten to ${reply.artifact.format}.`,
    );
  }
  for (const issue of reply.artifact.unparsed ?? []) {
    lines.push(issueLine(issue));
  }
  if (lines.length > 0) {
    return lines.join("\n");
  }
  if (reply.artifact.ok) {
    return "No errors found.";
  }
  return JSON.stringify(reply.artifact);
}

export function App() {
  const [rows, setRows] = useState<EventRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [turns, busy]);

  useEffect(() => {
    const input = inputRef.current;
    input?.focus();
    const holdFocus = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && input?.contains(target)) {
        return;
      }
      event.preventDefault();
      input?.focus();
    };
    document.addEventListener("pointerdown", holdFocus);
    return () => document.removeEventListener("pointerdown", holdFocus);
  }, []);

  function applyReport(reply: ChatReply) {
    if (!Array.isArray(reply.artifact.rows)) {
      return;
    }
    if (reply.artifact.ok === false) {
      setRows(null);
      setFailed(true);
      return;
    }
    setFailed(false);
    setRows(reply.artifact.rows);
  }

  async function send(message: string) {
    const text = message.trim();
    if (!text || busy) {
      return;
    }
    setBusy(true);
    setDraft("");
    setTurns((current) => [...current, { id: Date.now(), role: "user", text }]);
    try {
      const response = await fetch(`${COORDINATOR_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const body: unknown = await response.json();
      if (!response.ok) {
        const error =
          body && typeof body === "object" && "error" in body
            ? String((body as { error: string }).error)
            : response.statusText;
        throw new Error(error);
      }
      const reply = body as ChatReply;
      applyReport(reply);
      setTurns((current) => [
        ...current,
        { id: Date.now() + 1, role: "agent", text: describe(reply) },
      ]);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Chat failed.";
      setTurns((current) => [
        ...current,
        { id: Date.now() + 1, role: "agent", text: `Error: ${message}` },
      ]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Local events report</p>
        <h1>Cirque du Soleil — Drawn to Life</h1>
      </header>
      <section className="report" aria-live="polite">
        {failed ? (
          <div className="error">
            <h2>Cannot load the report</h2>
          </div>
        ) : rows === null ? (
          <p className="empty">No report loaded.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Event</th>
                <th>POS</th>
                <th>Listings</th>
                <th>Seats</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.event_date}-${row.listings}-${row.seats}`}>
                  <td>{row.event_date}</td>
                  <td>{row.event_name}</td>
                  <td>
                    {row.pos.split("|").map((name) => (
                      <span className={`badge ${name.toLowerCase()}`} key={name}>
                        {name}
                      </span>
                    ))}
                  </td>
                  <td>{row.listings}</td>
                  <td>{row.seats}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="terminal">
        <h2>Terminal</h2>
        <div className="log" ref={logRef}>
          {turns.map((turn) => (
            <p className={turn.role} key={turn.id}>
              {turn.role === "user" ? `$ ${turn.text}` : turn.text}
            </p>
          ))}
          {busy ? <p className="wait">...</p> : null}
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const message = new FormData(event.currentTarget).get("command");
            void send(typeof message === "string" ? message : "");
          }}
        >
          <span className="prompt" aria-hidden="true">
            $
          </span>
          <div className="term-entry">
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void send(event.currentTarget.value);
                }
              }}
              name="command"
              aria-label="Terminal command"
              autoComplete="off"
              spellCheck={false}
              autoFocus
            />
            <button type="submit" tabIndex={-1} aria-hidden="true">
              Send
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
