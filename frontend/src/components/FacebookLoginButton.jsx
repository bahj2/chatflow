import { useEffect, useState } from "react";
import { Facebook, Loader2 } from "lucide-react";
import { api, errMsg, BACKEND_URL } from "@/lib/auth";

/** "Continue with Facebook": signs in (or creates the shop) and shares the Facebook Page in the same step. Hidden until the platform Meta app is set up. */
export function FacebookLoginButton({ label = "Continue with Facebook", onError, testid = "facebook-login-btn" }) {
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/auth/facebook/available").then((r) => setOn(!!r.data.available)).catch(() => {}); }, []);
  if (!on) return null;
  const go = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/auth/facebook/start", { base_url: BACKEND_URL, return_url: window.location.origin });
      window.location.href = data.url;
    } catch (e) { onError?.(errMsg(e)); setBusy(false); }
  };
  return (
    <button type="button" onClick={go} disabled={busy} data-testid={testid} style={{ backgroundColor: "#1877F2" }}
      className="w-full rounded-full text-white py-3 font-semibold shadow-sm hover:brightness-110 transition flex items-center justify-center gap-2.5 disabled:opacity-60">
      {busy ? <Loader2 className="h-[18px] w-[18px] animate-spin" /> : <Facebook className="h-[18px] w-[18px]" fill="white" strokeWidth={0} />} {label}
    </button>
  );
}
