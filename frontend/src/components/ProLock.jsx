import { Link } from "react-router-dom";
import { Crown } from "lucide-react";

export const ProBadge = () => (
  <span className="inline-flex items-center gap-1 rounded-full bg-brand px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white"><Crown className="h-3 w-3" />Pro</span>
);

export const ProNote = ({ what, text, testid }) => (
  <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm" data-testid={testid}>
    <ProBadge />
    <span className="text-muted-foreground">{text || `${what} is included in the Pro and Business plans.`}</span>
    <Link to="/dashboard/billing" className="font-semibold text-primary hover:underline underline-offset-4" data-testid={`${testid}-upgrade-link`}>Upgrade</Link>
  </div>
);
