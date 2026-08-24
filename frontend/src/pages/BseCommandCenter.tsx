import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { authHeaders } from "@/lib/apiAuth";

type Center = {
  profile: string;
  company_name: string;
  instrument: string;
  advisory_only: boolean;
  auto_execution: boolean;
  operating: {
    mode: string;
    as_of: string;
    timezone: string;
    permissions: {
      observe_market: boolean;
      publish_advisory: boolean;
      fresh_day_entry_allowed: boolean;
      day_exit_priority: boolean;
      replay_allowed: boolean;
      challenger_research_allowed: boolean;
      broker_order_write_allowed: boolean;
      auto_promotion_allowed: boolean;
    };
  };
  guidance: null | {
    verdict?: string;
    mode?: string;
    direction?: string;
    entry?: number;
    target?: number;
    stop?: number;
    why?: string[];
    what_changes_verdict?: string[];
    data_gaps?: string[];
  };
  manual_trade_count: number;
  open_manual_trade_count: number;
  shadow_advisory_count: number;
  pending_shadow_count: number;
  kite: {
    sdk_available: boolean;
    api_key_configured: boolean;
    access_token_configured: boolean;
    authenticated_read_ready: boolean;
    read_only: boolean;
    broker_order_write_allowed: boolean;
  };
  external_gates: string[];
  calendar_source: string;
};

type ManualTrade = {
  trade_id: string;
  advisory_id: string;
  guidance_sha256: string;
  mode: string;
  direction: string;
  actual_entry: number;
  quantity: number;
  status: string;
  realized_pnl: number | null;
  opened_at: string;
};

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // keep HTTP status
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

function Flag({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${ok ? "bg-emerald-500/10 text-emerald-500" : "bg-amber-500/10 text-amber-500"}`}>
      {children}
    </span>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border/70 bg-card p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function BseCommandCenter() {
  const [center, setCenter] = useState<Center | null>(null);
  const [trades, setTrades] = useState<ManualTrade[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    advisory_id: "",
    guidance_sha256: "",
    mode: "day",
    direction: "long",
    planned_entry: "",
    planned_target: "",
    planned_stop: "",
    actual_entry: "",
    quantity: "",
    note: "",
  });

  const refresh = async () => {
    try {
      setError("");
      const [snapshot, manual] = await Promise.all([
        jsonRequest<Center>("/tradebrain/bse/command-center"),
        jsonRequest<ManualTrade[]>("/tradebrain/bse/journal/manual"),
      ]);
      setCenter(snapshot);
      setTrades(manual);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const openTrades = useMemo(() => trades.filter((trade) => trade.status === "open"), [trades]);

  const submitTrade = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await jsonRequest("/tradebrain/bse/journal/manual", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          planned_entry: Number(form.planned_entry),
          planned_target: Number(form.planned_target),
          planned_stop: Number(form.planned_stop),
          actual_entry: Number(form.actual_entry),
          quantity: Number(form.quantity),
        }),
      });
      setForm((old) => ({
        ...old,
        advisory_id: "",
        guidance_sha256: "",
        planned_entry: "",
        planned_target: "",
        planned_stop: "",
        actual_entry: "",
        quantity: "",
        note: "",
      }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 md:p-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">TradeBrain BSE</p>
          <h1 className="text-2xl font-semibold tracking-tight">BSE Command Center</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Advisory, shadow validation and your manual execution journal. No broker-order controls exist here.
          </p>
        </div>
        <button onClick={() => void refresh()} className="rounded-md border border-border px-3 py-2 text-sm hover:bg-muted">
          Refresh
        </button>
      </header>

      {error && <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Operating mode">
          <div className="text-lg font-semibold">{center?.operating.mode?.replaceAll("_", " ") || "—"}</div>
          <p className="mt-1 text-xs text-muted-foreground">{center?.operating.timezone || "Asia/Kolkata"}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Flag ok={Boolean(center?.operating.permissions.observe_market)}>market observe</Flag>
            <Flag ok={Boolean(center?.operating.permissions.fresh_day_entry_allowed)}>fresh DAY</Flag>
          </div>
        </Card>

        <Card title="Authoritative guidance">
          {center?.guidance ? (
            <>
              <div className="text-lg font-semibold">{center.guidance.verdict || "—"}</div>
              <p className="mt-1 text-xs text-muted-foreground">{center.guidance.mode} · {center.guidance.direction}</p>
            </>
          ) : (
            <>
              <div className="text-lg font-semibold">Not supplied</div>
              <p className="mt-1 text-xs text-muted-foreground">UI will not invent a verdict.</p>
            </>
          )}
        </Card>

        <Card title="Kite read-only">
          <div className="flex flex-wrap gap-2">
            <Flag ok={Boolean(center?.kite.authenticated_read_ready)}>data auth</Flag>
            <Flag ok={Boolean(center?.kite.read_only)}>read only</Flag>
            <Flag ok={center ? !center.kite.broker_order_write_allowed : true}>orders disabled</Flag>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">SDK/key/token status only. Secrets are never returned to this page.</p>
        </Card>

        <Card title="Evidence journal">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-xl font-semibold">{center?.manual_trade_count ?? 0}</div><div className="text-muted-foreground">manual</div></div>
            <div><div className="text-xl font-semibold">{center?.shadow_advisory_count ?? 0}</div><div className="text-muted-foreground">shadow</div></div>
            <div><div className="text-xl font-semibold">{center?.open_manual_trade_count ?? 0}</div><div className="text-muted-foreground">open</div></div>
            <div><div className="text-xl font-semibold">{center?.pending_shadow_count ?? 0}</div><div className="text-muted-foreground">pending</div></div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card title="External readiness gates">
          <div className="space-y-2">
            {(center?.external_gates || []).length === 0 ? (
              <p className="text-sm text-emerald-500">No external gates reported.</p>
            ) : (
              center?.external_gates.map((gate) => (
                <div key={gate} className="rounded-md bg-muted/50 px-3 py-2 text-sm">{gate.replaceAll("_", " ")}</div>
              ))
            )}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">Calendar source: {center?.calendar_source || "—"}</p>
        </Card>

        <Card title="Hard safety boundary">
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between"><span>Advisory only</span><Flag ok={Boolean(center?.advisory_only)}>locked</Flag></div>
            <div className="flex items-center justify-between"><span>Auto execution</span><Flag ok={center ? !center.auto_execution : true}>disabled</Flag></div>
            <div className="flex items-center justify-between"><span>Auto promotion</span><Flag ok={center ? !center.operating.permissions.auto_promotion_allowed : true}>disabled</Flag></div>
            <div className="flex items-center justify-between"><span>Broker write</span><Flag ok={center ? !center.operating.permissions.broker_order_write_allowed : true}>disabled</Flag></div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="I took this trade">
          <form onSubmit={submitTrade} className="grid gap-3 md:grid-cols-2">
            {[
              ["advisory_id", "Advisory ID"],
              ["guidance_sha256", "Guidance SHA-256"],
              ["planned_entry", "Planned entry"],
              ["planned_target", "Planned target"],
              ["planned_stop", "Planned stop"],
              ["actual_entry", "Actual entry"],
              ["quantity", "Quantity"],
            ].map(([key, label]) => (
              <label key={key} className="space-y-1 text-xs text-muted-foreground">
                <span>{label}</span>
                <input required value={form[key as keyof typeof form]} onChange={(event) => setForm((old) => ({ ...old, [key]: event.target.value }))} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/30" />
              </label>
            ))}
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>Mode</span>
              <select value={form.mode} onChange={(event) => setForm((old) => ({ ...old, mode: event.target.value }))} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground">
                <option value="day">DAY</option><option value="swing">SWING</option>
              </select>
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>Direction</span>
              <select value={form.direction} onChange={(event) => setForm((old) => ({ ...old, direction: event.target.value }))} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground">
                <option value="long">LONG</option><option value="short">SHORT</option>
              </select>
            </label>
            <label className="space-y-1 text-xs text-muted-foreground md:col-span-2">
              <span>Note</span>
              <input value={form.note} onChange={(event) => setForm((old) => ({ ...old, note: event.target.value }))} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground" />
            </label>
            <button disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 md:col-span-2">{saving ? "Saving…" : "Record manual trade"}</button>
          </form>
        </Card>

        <Card title={`Open manual trades (${openTrades.length})`}>
          <div className="space-y-2">
            {openTrades.length === 0 ? <p className="text-sm text-muted-foreground">No open manual trades.</p> : openTrades.map((trade) => (
              <div key={trade.trade_id} className="rounded-lg border border-border/60 p-3 text-sm">
                <div className="flex items-center justify-between"><span className="font-medium">{trade.mode.toUpperCase()} {trade.direction.toUpperCase()}</span><span className="text-muted-foreground">Qty {trade.quantity}</span></div>
                <div className="mt-1 text-xs text-muted-foreground">Entry ₹{trade.actual_entry.toFixed(2)} · advisory {trade.advisory_id}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
