import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/auth";

const BillingCtx = createContext({ billing: null, refresh: () => {} });

export const BillingProvider = ({ children }) => {
  const [billing, setBilling] = useState(null);
  const refresh = useCallback(() => api.get("/billing").then((r) => setBilling(r.data)).catch(() => {}), []);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 60000);
    return () => clearInterval(t);
  }, [refresh]);
  return <BillingCtx.Provider value={{ billing, refresh }}>{children}</BillingCtx.Provider>;
};

export const useBilling = () => useContext(BillingCtx);

// true / false once known, undefined while loading
export const usePro = () => useContext(BillingCtx).billing?.sub.pro;

export const PLAN_FEATURES = {
  starter: ["1 Telegram bot + 1 Facebook page", "Products with photos", "Bakong KHQR payments", "Understands voice messages (answers in text)", "AI customer summaries & suggested replies", "1 login"],
  pro: ["Everything in Starter", "Voice replies to voice messages (Khmer)", "Seller voice clone", "Notion knowledge base", "3 logins"],
  business: ["Everything in Pro", "10 logins", "Priority support", "We set up your shop for you"],
};
