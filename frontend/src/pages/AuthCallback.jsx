import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth, errMsg } from "@/lib/auth";

export default function AuthCallback() {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const { loginGoogle, failGoogle } = useAuth();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const sid = new URLSearchParams(hash.slice(1)).get("session_id");
    loginGoogle(sid)
      .then((d) => {
        if (d?.password_off) toast.info("Google confirmed this email is yours, so the password set at sign-up was turned off for your safety. Use Continue with Google to sign in.", { duration: 10000 });
        navigate("/dashboard", { replace: true });
      })
      .catch((e) => {
        failGoogle();
        navigate("/login", { replace: true, state: { error: errMsg(e) } });
      });
  }, [hash, loginGoogle, failGoogle, navigate]);

  return <div className="min-h-screen grid place-items-center text-muted-foreground" data-testid="auth-callback">Signing you in…</div>;
}
