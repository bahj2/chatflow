import { useEffect } from "react";
import { Loader2 } from "lucide-react";

/** Runs inside the small Facebook window: tells the Channels page what happened, then closes itself. */
export default function FacebookDone() {
  const q = new URLSearchParams(window.location.search);
  const loading = q.get("loading");

  useEffect(() => {
    if (loading) return;
    const msg = { source: "replyflow-fb", fb: q.get("fb"), fb_error: q.get("fb_error") };
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage(msg, window.location.origin);
      window.close();
    } else {
      // opened as a normal tab (some phones): continue right here
      q.delete("loading");
      window.location.replace(`/dashboard/channels?${q.toString()}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen grid place-items-center bg-background text-muted-foreground" data-testid="fb-done">
      <p className="flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> {loading ? "Opening Facebook…" : "Connecting your Page…"}</p>
    </div>
  );
}
