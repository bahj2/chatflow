import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useAuth, errMsg } from "@/lib/auth";

/** Back from Facebook: swap the one-time code for a session, then go straight to the right screen. */
export default function FacebookAuth() {
  const [params] = useSearchParams();
  const { loginFacebook } = useAuth();
  const navigate = useNavigate();
  const once = useRef(false);

  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const code = params.get("code");
    if (!code) { navigate("/login", { replace: true }); return; }
    loginFacebook(code)
      .then((d) => {
        if (d.password_off) toast.info("Facebook confirmed this email is yours, so the password set at sign-up was turned off for your safety. Use Continue with Facebook or Google to sign in.", { duration: 10000 });
        else if (d.new) toast.success("Welcome to Replyflow AI! Your shop is ready.");
        navigate(d.pending_pages ? "/dashboard/channels" : "/dashboard", { replace: true });
      })
      .catch((e) => navigate("/login", { replace: true, state: { error: errMsg(e) } }));
  }, [params, loginFacebook, navigate]);

  return (
    <div className="min-h-screen grid place-items-center bg-background text-muted-foreground" data-testid="facebook-auth">
      <p className="flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Signing you in with Facebook…</p>
    </div>
  );
}
