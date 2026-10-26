import { NavLink, Routes, Route, Link, Navigate } from "react-router-dom";
import { Inbox as InboxIcon, Settings2, Plug, LogOut, ExternalLink, Building2, Package, Receipt } from "lucide-react";
import { BrandMark, BRAND } from "@/components/Brand";
import { useAuth } from "@/lib/auth";
import Inbox from "@/components/Inbox";
import SettingsPanel from "@/components/SettingsPanel";
import ChannelsPanel from "@/components/ChannelsPanel";
import AdminPanel from "@/components/AdminPanel";
import ProductsPanel from "@/components/ProductsPanel";
import OrdersPanel from "@/components/OrdersPanel";

const NAV = [
  { to: "/dashboard", label: "Inbox", Icon: InboxIcon, end: true, id: "inbox" },
  { to: "/dashboard/products", label: "Products", Icon: Package, id: "products" },
  { to: "/dashboard/orders", label: "Orders", Icon: Receipt, id: "orders" },
  { to: "/dashboard/settings", label: "AI Settings", Icon: Settings2, id: "settings" },
  { to: "/dashboard/channels", label: "Channels", Icon: Plug, id: "channels" },
];

export default function Dashboard() {
  const { user, logout } = useAuth();
  const nav = user.role === "superadmin" ? [...NAV, { to: "/dashboard/businesses", label: "Businesses", Icon: Building2, id: "businesses" }] : NAV;
  return (
    <div className="h-screen flex flex-col md:flex-row bg-[#0B0F17]">
      <aside className="md:w-20 lg:w-56 shrink-0 border-b md:border-b-0 md:border-r border-white/5 bg-[#0D121C] flex md:flex-col items-center lg:items-stretch gap-1 p-3">
        <Link to="/" className="flex items-center gap-2 font-display font-bold px-2 py-2 md:mb-6" data-testid="dash-logo">
          <BrandMark />
          <span className="hidden lg:inline">{BRAND}</span>
        </Link>
        {user.role !== "superadmin" && <span className="md:hidden flex-1 min-w-0 text-sm font-semibold truncate" data-testid="dash-business-name-mobile">{user.business_name}</span>}
        <div className="hidden lg:block px-3 pb-4 -mt-3" data-testid="dash-business-name">
          <p className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Business</p>
          <p className="text-sm font-semibold truncate">{user.business_name}</p>
        </div>
        <nav className={`flex md:flex-col gap-1 md:flex-1 ${user.role === "superadmin" ? "flex-1" : ""}`}>
          {nav.map(({ to, label, Icon, end, id }) => (
            <NavLink key={to} to={to} end={end} data-testid={`nav-${id}`}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive ? "bg-emerald-500/10 text-emerald-400" : "text-slate-400 hover:text-white hover:bg-white/5"}`}>
              <Icon className="h-4 w-4" /><span className="hidden lg:inline">{label}</span>
            </NavLink>
          ))}
        </nav>
        <a href="/" target="_blank" rel="noreferrer" className="hidden md:flex items-center gap-3 px-3 py-2.5 text-sm text-slate-400 hover:text-white" data-testid="nav-view-site">
          <ExternalLink className="h-4 w-4" /><span className="hidden lg:inline">View website</span>
        </a>
        <button onClick={logout} data-testid="logout-btn" className="flex items-center gap-3 px-3 py-2.5 text-sm text-slate-400 hover:text-red-400">
          <LogOut className="h-4 w-4" /><span className="hidden lg:inline">Log out</span>
        </button>
      </aside>
      <main className="flex-1 min-h-0 min-w-0">
        <Routes>
          <Route index element={<Inbox />} />
          <Route path="settings" element={<SettingsPanel />} />
          <Route path="channels" element={<ChannelsPanel />} />
          <Route path="products" element={<ProductsPanel />} />
          <Route path="orders" element={<OrdersPanel />} />
          {user.role === "superadmin" && <Route path="businesses" element={<AdminPanel />} />}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
