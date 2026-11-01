import { useState } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { Inbox as InboxIcon, Package, Receipt, Settings2, Menu, Plug, CreditCard, Building2, PlayCircle, ExternalLink, LogOut, ChevronRight } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useBilling } from "@/lib/billing";

const TABS = [
  { to: "/dashboard", label: "Inbox", Icon: InboxIcon, end: true, id: "inbox" },
  { to: "/dashboard/products", label: "Products", Icon: Package, id: "products" },
  { to: "/dashboard/orders", label: "Orders", Icon: Receipt, id: "orders" },
  { to: "/dashboard/settings", label: "Settings", Icon: Settings2, id: "settings" },
];

const tabCls = (on) => `relative flex flex-1 flex-col items-center justify-center gap-1 py-2 text-[11px] font-semibold transition-colors ${on ? "text-primary" : "text-muted-foreground"}`;

const Row = ({ Icon, label, sub, testid, danger, ...props }) => {
  const Tag = props.to ? Link : props.href ? "a" : "button";
  return (
    <Tag {...props} data-testid={testid}
      className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3.5 text-left transition-colors hover:bg-muted ${danger ? "text-red-600 dark:text-red-400" : ""}`}>
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${danger ? "bg-red-500/10" : "bg-primary/10 text-primary"}`}><Icon className="h-5 w-5" /></span>
      <span className="min-w-0 flex-1"><span className="block text-[15px] font-semibold">{label}</span>{sub && <span className="block truncate text-xs text-muted-foreground">{sub}</span>}</span>
      {!danger && <ChevronRight className="h-4 w-4 text-muted-foreground" />}
    </Tag>
  );
};

const planSub = (s) => (!s ? "" : s.exempt ? "Platform · unlimited" : s.paused ? `${s.plan_name} · AI paused` : `${s.plan_name} · ${s.days_left} days left`);

export const MobileTabs = ({ admin, onTutorial, onLogout }) => {
  const [open, setOpen] = useState(false);
  const sub = useBilling().billing?.sub;
  const close = () => setOpen(false);
  const inMore = /^\/dashboard\/(channels|billing|businesses)/.test(useLocation().pathname);
  return (
    <>
      <nav className="md:hidden shrink-0 border-t border-border bg-surface/95 backdrop-blur-xl pb-[env(safe-area-inset-bottom)]" data-testid="mobile-tabbar">
        <div className="flex">
          {TABS.map(({ to, label, Icon, end, id }) => (
            <NavLink key={id} to={to} end={end} className={({ isActive }) => tabCls(isActive)} data-testid={`tab-${id}`}>
              {({ isActive }) => (<>
                {isActive && <span className="absolute top-0 h-0.5 w-8 rounded-full bg-brand" />}
                <Icon className="h-[22px] w-[22px]" />{label}
              </>)}
            </NavLink>
          ))}
          <button onClick={() => setOpen(true)} className={tabCls(open || inMore)} data-testid="tab-more">
            {inMore && <span className="absolute top-0 h-0.5 w-8 rounded-full bg-brand" />}<Menu className="h-[22px] w-[22px]" />More</button>
        </div>
      </nav>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" onOpenAutoFocus={(e) => e.preventDefault()} className="rounded-t-3xl border-border bg-card px-3 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-3" data-testid="mobile-more-sheet">
          <div className="mx-auto mb-2 h-1.5 w-10 rounded-full bg-muted" />
          <SheetHeader className="px-4 pb-1 text-left"><SheetTitle className="font-display">More</SheetTitle></SheetHeader>
          <div className="space-y-0.5">
            <Row Icon={Plug} label="Channels" sub="Telegram and Messenger" to="/dashboard/channels" onClick={close} testid="more-channels" />
            <Row Icon={CreditCard} label="Billing" sub={planSub(sub)} to="/dashboard/billing" onClick={close} testid="more-billing" />
            {admin && <Row Icon={Building2} label="Businesses" sub="Platform admin" to="/dashboard/businesses" onClick={close} testid="more-businesses" />}
            <Row Icon={PlayCircle} label="Watch tutorial" sub="2-minute video in Khmer" onClick={() => { close(); onTutorial(); }} testid="more-tutorial" />
            <Row Icon={ExternalLink} label="Website" href="/" target="_blank" rel="noreferrer" testid="more-website" />
            <div className="mx-4 my-1 border-t border-border" />
            <Row Icon={LogOut} label="Log out" danger onClick={onLogout} testid="more-logout" />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
};
