import { useState } from "react";
import { NavLink, Routes, Route, Link, Navigate } from "react-router-dom";
import { Inbox as InboxIcon, Settings2, Plug, LogOut, ExternalLink, Building2, Package, Receipt, CreditCard, PauseCircle, PlayCircle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { TourVideo } from "@/components/LandingPricing";
import { MobileTabs } from "@/components/MobileTabs";
import { BrandMark, BRAND } from "@/components/Brand";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";
import { BillingProvider, useBilling } from "@/lib/billing";
import Inbox from "@/components/Inbox";
import SettingsPanel from "@/components/SettingsPanel";
import ChannelsPanel from "@/components/ChannelsPanel";
import AdminPanel from "@/components/AdminPanel";
import ProductsPanel from "@/components/ProductsPanel";
import OrdersPanel from "@/components/OrdersPanel";
import BillingPanel from "@/components/BillingPanel";

const NAV = [
  { to: "/dashboard", label: "Inbox", Icon: InboxIcon, end: true, id: "inbox", group: "Workspace" },
  { to: "/dashboard/products", label: "Products", Icon: Package, id: "products" },
  { to: "/dashboard/orders", label: "Orders", Icon: Receipt, id: "orders" },
  { to: "/dashboard/settings", label: "AI Settings", Icon: Settings2, id: "settings", group: "Setup" },
  { to: "/dashboard/channels", label: "Channels", Icon: Plug, id: "channels" },
  { to: "/dashboard/billing", label: "Billing", Icon: CreditCard, id: "billing" },
];

const PlanChip = () => {
  const s = useBilling().billing?.sub;
  if (!s) return null;
  const tone = s.paused ? "bg-red-500" : s.exempt || s.days_left > 5 ? "bg-emerald-500" : "bg-amber-500";
  return (
    <Link to="/dashboard/billing" className="hidden lg:block rounded-2xl border border-border bg-card px-3 py-2.5 mb-2 transition-colors duration-200 hover:border-primary/40" data-testid="sidebar-plan-chip">
      <span className="flex items-center justify-between gap-2 text-sm font-semibold"><span className="truncate">{s.exempt ? "Platform" : s.plan_name}</span><span className={`h-2 w-2 shrink-0 rounded-full ${tone}`} /></span>
      <span className="block text-[11px] text-muted-foreground mt-0.5">{s.exempt ? "Unlimited AI replies" : s.paused ? "AI replies paused" : `${s.days_left} days left · ${s.used.toLocaleString()}/${s.limit.toLocaleString()} replies`}</span>
    </Link>
  );
};

const PausedBanner = () => {
  const s = useBilling().billing?.sub;
  if (!s?.paused) return null;
  const why = s.reason === "ended" ? (s.plan === "trial" ? "Your free trial has ended." : `Your ${s.plan_name} plan has ended.`) : `You've used all ${s.limit.toLocaleString()} AI replies for this month.`;
  return (
    <div className="shrink-0 flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-red-500/30 bg-red-500/10 px-5 py-2.5 text-sm text-red-700 dark:text-red-300" data-testid="paused-banner">
      <PauseCircle className="h-4 w-4 shrink-0" />
      <span><b>AI replies are paused.</b> {why} Customer messages still arrive and you can reply yourself.</span>
      <Link to="/dashboard/billing" className="font-semibold underline underline-offset-4" data-testid="paused-banner-link">{s.reason === "used_up" ? "Buy more replies" : "Choose a plan"}</Link>
    </div>
  );
};

const item = "relative flex items-center gap-3 rounded-xl px-2.5 md:px-3 py-2.5 text-sm font-medium transition-colors";

const TutorialDialog = ({ open, setOpen }) => (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-3xl p-3" data-testid="tutorial-dialog">
        <DialogHeader className="px-2 pt-1"><DialogTitle className="font-display">How to use Replyflow AI</DialogTitle></DialogHeader>
        <TourVideo />
      </DialogContent>
    </Dialog>
);

const BusinessCard = ({ name }) => (
  <div className="hidden lg:flex items-center gap-3 rounded-2xl border border-border bg-card px-3 py-2.5 mb-5" data-testid="dash-business-name">
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand font-display font-bold text-white">{(name || "?").trim()[0]?.toUpperCase()}</span>
    <div className="min-w-0">
      <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Business</p>
      <p className="text-sm font-semibold truncate">{name}</p>
    </div>
  </div>
);

const SideNav = ({ nav, grow }) => (
  <nav className={`hidden md:flex md:flex-col gap-1 md:flex-1 min-w-0 overflow-x-auto md:overflow-visible [scrollbar-width:none] ${grow ? "flex-1" : ""}`}>
    {nav.map(({ to, label, Icon, end, id, group }) => (
      <div key={to} className="contents">
        {group && <p className={`hidden lg:block px-3 pb-1.5 text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground/70 ${id === "inbox" ? "" : "pt-4"}`}>{group}</p>}
        <NavLink to={to} end={end} data-testid={`nav-${id}`} title={label}
          className={({ isActive }) => `${item} ${isActive ? "bg-primary/10 text-primary font-semibold" : "text-muted-foreground hover:text-foreground hover:bg-muted/70"}`}>
          {({ isActive }) => (<>
            {isActive && <span className="absolute left-0 top-1/2 hidden h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand md:block" />}
            <Icon className="h-[18px] w-[18px] shrink-0" /><span className="hidden lg:inline">{label}</span>
          </>)}
        </NavLink>
      </div>
    ))}
  </nav>
);

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [tut, setTut] = useState(false);
  const nav = user.role === "superadmin" ? [...NAV, { to: "/dashboard/businesses", label: "Businesses", Icon: Building2, id: "businesses", group: "Admin" }] : NAV;
  return (
    <BillingProvider>
    <div className="h-[100dvh] flex flex-col md:flex-row bg-background">
      <aside className="md:w-20 lg:w-64 shrink-0 border-b md:border-b-0 md:border-r border-border bg-surface flex md:flex-col items-center lg:items-stretch gap-1 px-2 py-2 md:p-3 lg:p-4">
        <Link to="/" className="flex shrink-0 items-center gap-2.5 font-display font-bold text-[17px] px-1.5 md:px-2 py-2 md:mb-5" data-testid="dash-logo">
          <BrandMark />
          <span className="hidden lg:inline">{BRAND}</span>
        </Link>
        <span className="md:hidden flex-1 min-w-0 text-sm font-semibold truncate" data-testid="dash-business-name-mobile">{user.role === "superadmin" ? BRAND : user.business_name}</span>
        <BusinessCard name={user.business_name} />
        <SideNav nav={nav} grow={user.role === "superadmin"} />
        <PlanChip />
        <div className="flex md:flex-col lg:flex-row items-center lg:items-stretch gap-1 md:gap-2 md:pt-3 md:border-t md:border-border">
          <a href="/" target="_blank" rel="noreferrer" title="View website" className={`hidden md:flex ${item} text-muted-foreground hover:text-foreground hover:bg-muted/70 lg:flex-1`} data-testid="nav-view-site">
            <ExternalLink className="h-[18px] w-[18px]" /><span className="hidden lg:inline">Website</span>
          </a>
          <button onClick={() => setTut(true)} title="Watch tutorial" data-testid="nav-tutorial-btn" className="hidden md:grid h-9 w-9 shrink-0 place-items-center rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/70 transition-colors"><PlayCircle className="h-[18px] w-[18px]" /></button>
          <ThemeToggle />
        </div>
        <button onClick={logout} data-testid="logout-btn" title="Log out" className={`${item} hidden md:flex shrink-0 text-muted-foreground hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10`}>
          <LogOut className="h-[18px] w-[18px]" /><span className="hidden lg:inline">Log out</span>
        </button>
      </aside>
      <main className="flex-1 min-h-0 min-w-0 flex flex-col">
        <PausedBanner />
        <div className="flex-1 min-h-0">
        <Routes>
          <Route index element={<Inbox />} />
          <Route path="settings" element={<SettingsPanel />} />
          <Route path="channels" element={<ChannelsPanel />} />
          <Route path="products" element={<ProductsPanel />} />
          <Route path="orders" element={<OrdersPanel />} />
          <Route path="billing" element={<BillingPanel />} />
          {user.role === "superadmin" && <Route path="businesses" element={<AdminPanel />} />}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </div>
      </main>
      <MobileTabs admin={user.role === "superadmin"} onTutorial={() => setTut(true)} onLogout={logout} />
      <TutorialDialog open={tut} setOpen={setTut} />
    </div>
    </BillingProvider>
  );
}
