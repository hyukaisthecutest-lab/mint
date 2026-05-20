import { useEffect, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";
import { Activity, Zap, AlertTriangle, Shield, Cpu, Clock } from "lucide-react";
import { useAuthStore } from "../store/authStore";

interface ActivityEntry {
  ts: number;
  user_id: string;
  message: string;
  status: "active" | "ok" | "error";
  latency_ms: number | null;
}

interface Snapshot {
  ts: number;
  active: number;
  req_per_min: number;
  err_per_min: number;
  error_rate_pct: number;
  latency: { avg: number; p95: number; p99: number };
  blocked_per_min: number;
  tool_calls: Record<string, number>;
  tokens: { prompt: number; completion: number };
  activity: ActivityEntry[];
}

const MAX_HISTORY = 40;
const TOOL_COLORS = ["#00A651", "#22c55e", "#60a5fa", "#f87171", "#fbbf24", "#a78bfa"];

function healthColor(errorRate: number) {
  if (errorRate < 5) return "bg-green-500";
  if (errorRate < 20) return "bg-yellow-500";
  return "bg-red-500";
}

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string; sub?: string; icon: any; color: string;
}) {
  return (
    <div className="card flex items-start gap-4">
      <div className={`p-2.5 rounded-lg ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function AgentDashboard() {
  const token = useAuthStore((s) => s.token);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [latest, setLatest] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/agent/status/ws?token=${token}`);
    esRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onmessage = (e) => {
      const snap: Snapshot = JSON.parse(e.data);
      setLatest(snap);
      setHistory((h) => [...h.slice(-MAX_HISTORY + 1), snap]);
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    return () => ws.close();
  }, [token]);

  const chartData = history.map((s) => ({
    t: new Date(s.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    rpm: s.req_per_min,
    avg: s.latency.avg,
    p95: s.latency.p95,
    err: s.err_per_min,
  }));

  const toolData = latest
    ? Object.entries(latest.tool_calls).map(([name, count]) => ({
        name: name.replace("get_", "").replace(/_/g, " "),
        count,
      }))
    : [];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Agent Dashboard</h1>
          <p className="text-gray-500 mt-1">Real-time — updates every 3s</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${connected ? "bg-green-500 animate-pulse" : "bg-red-400"}`} />
          <span className="text-sm text-gray-500">{connected ? "Live" : "Disconnected"}</span>
          {latest && (
            <span className={`ml-4 w-3 h-3 rounded-full ${healthColor(latest.error_rate_pct)}`} title="Health" />
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
        <StatCard
          label="Active"
          value={String(latest?.active ?? 0)}
          sub="requests"
          icon={Activity}
          color="bg-mint-600"
        />
        <StatCard
          label="Req / min"
          value={String(latest?.req_per_min ?? 0)}
          icon={Zap}
          color="bg-blue-500"
        />
        <StatCard
          label="Avg latency"
          value={latest ? `${latest.latency.avg}ms` : "—"}
          sub={latest ? `p95: ${latest.latency.p95}ms` : undefined}
          icon={Clock}
          color="bg-purple-500"
        />
        <StatCard
          label="Error rate"
          value={latest ? `${latest.error_rate_pct}%` : "—"}
          sub={`${latest?.err_per_min ?? 0} err/min`}
          icon={AlertTriangle}
          color={latest && latest.error_rate_pct >= 5 ? "bg-red-500" : "bg-gray-400"}
        />
        <StatCard
          label="Blocked"
          value={String(latest?.blocked_per_min ?? 0)}
          sub="per min"
          icon={Shield}
          color="bg-orange-500"
        />
        <StatCard
          label="Tokens"
          value={latest ? String(latest.tokens.prompt + latest.tokens.completion) : "—"}
          sub={latest ? `${latest.tokens.prompt}p / ${latest.tokens.completion}c` : undefined}
          icon={Cpu}
          color="bg-teal-500"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Requests / min</h2>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData}>
              <XAxis dataKey="t" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10 }} width={30} />
              <Tooltip />
              <Line type="monotone" dataKey="rpm" stroke="#00A651" strokeWidth={2} dot={false} name="req/min" />
              <Line type="monotone" dataKey="err" stroke="#f87171" strokeWidth={1.5} dot={false} name="err/min" strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Latency (ms)</h2>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData}>
              <XAxis dataKey="t" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10 }} width={40} unit="ms" />
              <Tooltip />
              <Line type="monotone" dataKey="avg" stroke="#60a5fa" strokeWidth={2} dot={false} name="avg" />
              <Line type="monotone" dataKey="p95" stroke="#a78bfa" strokeWidth={1.5} dot={false} name="p95" strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tool calls */}
      <div className="card mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Tool Calls (all time)</h2>
        {toolData.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-6">No tool calls recorded yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={toolData} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={160} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {toolData.map((_, i) => (
                  <Cell key={i} fill={TOOL_COLORS[i % TOOL_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* User activity */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent User Activity</h2>
        {(!latest?.activity?.length) ? (
          <p className="text-gray-400 text-sm text-center py-6">No activity yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-400 uppercase border-b border-gray-100">
                  <th className="text-left pb-2 pr-4">Time</th>
                  <th className="text-left pb-2 pr-4">User ID</th>
                  <th className="text-left pb-2 pr-4">Message</th>
                  <th className="text-left pb-2 pr-4">Status</th>
                  <th className="text-right pb-2">Latency</th>
                </tr>
              </thead>
              <tbody>
                {latest.activity.map((a, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-4 text-gray-400 font-mono text-xs whitespace-nowrap">
                      {new Date(a.ts).toLocaleTimeString()}
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs text-gray-500 whitespace-nowrap">
                      {a.user_id.slice(0, 8)}…
                    </td>
                    <td className="py-2 pr-4 text-gray-700 max-w-xs truncate">{a.message}</td>
                    <td className="py-2 pr-4">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        a.status === "ok" ? "bg-green-100 text-green-700" :
                        a.status === "error" ? "bg-red-100 text-red-700" :
                        "bg-yellow-100 text-yellow-700"
                      }`}>
                        {a.status === "active" ? "⏳ active" : a.status === "ok" ? "✓ ok" : "✗ error"}
                      </span>
                    </td>
                    <td className="py-2 text-right text-gray-400 font-mono text-xs">
                      {a.latency_ms != null ? `${a.latency_ms}ms` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
