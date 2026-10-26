import { useEffect, useMemo, useState } from "react";
import { Building2, Search, MessagesSquare, Bot, Send, Facebook } from "lucide-react";
import { api } from "@/lib/auth";

const Stat = ({ label, value, testid }) => (
  <div className="rounded-xl border border-border bg-card p-5">
    <p className="text-xs text-muted-foreground">{label}</p>
    <p className="font-display text-3xl font-bold mt-1" data-testid={testid}>{value.toLocaleString()}</p>
  </div>
);

export default function AdminPanel() {
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => { api.get("/admin/businesses").then((r) => setRows(r.data)); }, []);
  const list = useMemo(() => (rows || []).filter((b) => `${b.name} ${b.owner_email}`.toLowerCase().includes(q.toLowerCase())), [rows, q]);
  if (!rows) return <div className="p-8 text-muted-foreground/80">Loading…</div>;
  const sum = (k) => rows.reduce((a, b) => a + b[k], 0);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h1 className="font-display text-3xl font-bold flex items-center gap-3"><Building2 className="h-7 w-7 text-emerald-600 dark:text-emerald-400" /> Businesses</h1>
          <p className="text-sm text-muted-foreground mt-1">Every business using ReplyFlow. Only you (platform admin) can see this page.</p>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Businesses" value={rows.length} testid="admin-stat-businesses" />
          <Stat label="Conversations" value={sum("conversations")} testid="admin-stat-conversations" />
          <Stat label="AI replies" value={sum("ai_replies")} testid="admin-stat-ai" />
          <Stat label="Telegram bots connected" value={rows.filter((b) => b.telegram).length} testid="admin-stat-telegram" />
        </div>
        <div className="relative max-w-sm">
          <Search className="h-4 w-4 absolute left-3 top-2.5 text-muted-foreground/80" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search business or owner…" data-testid="admin-search-input"
            className="w-full bg-muted/50 border border-border rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-emerald-500/60" />
        </div>
        <div className="rounded-xl border border-border overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]" data-testid="admin-businesses-table">
            <thead className="bg-card text-xs text-muted-foreground text-left">
              <tr><th className="px-4 py-3">Business</th><th className="px-4 py-3">Owner</th><th className="px-4 py-3">Channels</th>
                <th className="px-4 py-3 text-right">Chats</th><th className="px-4 py-3 text-right">AI replies</th><th className="px-4 py-3">Joined</th></tr>
            </thead>
            <tbody>
              {list.map((b) => (
                <tr key={b.id} className="border-t border-border/60 hover:bg-muted/30" data-testid={`admin-business-row-${b.id}`}>
                  <td className="px-4 py-3 font-semibold">{b.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{b.owner_email}</td>
                  <td className="px-4 py-3">
                    <span className="flex gap-2">
                      <Send className={`h-4 w-4 ${b.telegram ? "text-[#229ED9]" : "text-muted-foreground/40"}`} />
                      <Facebook className={`h-4 w-4 ${b.messenger ? "text-[#0084FF]" : "text-muted-foreground/40"}`} />
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right"><span className="inline-flex items-center gap-1"><MessagesSquare className="h-3.5 w-3.5 text-muted-foreground/80" />{b.conversations.toLocaleString()}</span></td>
                  <td className="px-4 py-3 text-right"><span className="inline-flex items-center gap-1"><Bot className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />{b.ai_replies.toLocaleString()}</span></td>
                  <td className="px-4 py-3 text-muted-foreground">{new Date(b.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
              {list.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/80">No businesses found</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
