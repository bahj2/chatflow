import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Plus, Pencil, Trash2, ImagePlus, Loader2, Package, Search } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { StockPill, StockStepper, SummaryCards, CategoryChips, stockState } from "@/components/ProductParts";

const EMPTY = { name: "", price: "", description: "", image_media_id: "", category: "", stock: null };
const Label = ({ children }) => <span className="text-xs font-medium text-muted-foreground mb-1.5 block">{children}</span>;

const StockField = ({ f, setF }) => {
  const on = f.stock != null;
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div><p className="text-sm font-medium">Track stock</p><p className="text-[11px] text-muted-foreground">Goes down by itself when an order is paid. At 0 the AI says it&apos;s sold out.</p></div>
        <Switch checked={on} onCheckedChange={(v) => setF((x) => ({ ...x, stock: v ? 10 : null }))} data-testid="product-stock-switch" />
      </div>
      {on && <Input type="number" min={0} value={f.stock} onChange={(e) => setF((x) => ({ ...x, stock: e.target.value === "" ? "" : Math.max(0, parseInt(e.target.value, 10) || 0) }))} data-testid="product-stock-input" placeholder="Units in stock" />}
    </div>
  );
};

const ProductForm = ({ initial, cats, onClose, onSaved }) => {
  const [f, setF] = useState({ ...EMPTY, ...(initial || {}) });
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/media/image", fd);
      setF((x) => ({ ...x, image_media_id: data.id }));
    } catch (e) { toast.error(errMsg(e)); } finally { setUploading(false); }
  };
  const save = async () => {
    if (!f.name.trim()) return toast.error("Product name is required");
    setSaving(true);
    try {
      const body = { name: f.name, price: f.price, description: f.description, image_media_id: f.image_media_id, category: f.category.trim(), stock: f.stock === "" ? 0 : f.stock };
      if (initial?.id) await api.put(`/products/${initial.id}`, body); else await api.post("/products", body);
      toast.success("Product saved");
      onSaved();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-card border-border max-w-xl max-h-[92dvh] overflow-y-auto" data-testid="product-dialog">
        <DialogHeader><DialogTitle className="font-display">{initial?.id ? "Edit product" : "Add product"}</DialogTitle></DialogHeader>
        <div className="grid sm:grid-cols-[170px_1fr] gap-4">
          <button type="button" onClick={() => fileRef.current?.click()} data-testid="product-image-btn"
            className="h-44 rounded-xl border border-dashed border-foreground/15 bg-muted/50 grid place-items-center overflow-hidden hover:border-primary/50 transition-colors">
            {uploading ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              : f.image_media_id ? <img src={mediaUrl(f.image_media_id)} alt="" className="h-full w-full object-cover" data-testid="product-image-preview" />
              : <span className="text-xs text-muted-foreground flex flex-col items-center gap-2"><ImagePlus className="h-6 w-6" />Add photo</span>}
          </button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" data-testid="product-image-input" onChange={(e) => upload(e.target.files?.[0])} />
          <div className="space-y-3">
            <label className="block"><Label>Name</Label><Input placeholder="Product name" value={f.name} onChange={set("name")} data-testid="product-name-input" /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><Label>Price</Label><Input placeholder="$25 or 100,000 ៛" value={f.price} onChange={set("price")} data-testid="product-price-input" /></label>
              <label className="block"><Label>Category</Label><Input list="product-cats" maxLength={40} placeholder="e.g. Shoes" value={f.category} onChange={set("category")} data-testid="product-category-input" />
                <datalist id="product-cats">{cats.map((c) => <option key={c} value={c} />)}</datalist></label>
            </div>
          </div>
        </div>
        <label className="block"><Label>Description</Label><Textarea rows={3} placeholder="Size, colour, material… (helps the AI pick the right product)" value={f.description} onChange={set("description")} data-testid="product-description-input" /></label>
        <StockField f={f} setF={setF} />
        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="rounded-full px-5 py-2 text-sm text-foreground/80 hover:bg-muted/60" data-testid="product-cancel-btn">Cancel</button>
          <button onClick={save} disabled={saving || uploading} data-testid="product-save-btn"
            className="rounded-full btn-brand px-5 py-2 text-sm font-semibold disabled:opacity-60">{saving ? "Saving…" : "Save product"}</button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const ProductCard = ({ p, onEdit, onDelete, onStock }) => (
  <div className={`group rounded-2xl overflow-hidden border border-border bg-card card-shadow transition-[transform,border-color] duration-200 hover:-translate-y-0.5 hover:border-primary/30 ${stockState(p) === "out" ? "opacity-75" : ""}`} data-testid={`product-card-${p.id}`}>
    <div className="aspect-square bg-muted/50 relative">
      {p.image_media_id ? <img src={mediaUrl(p.image_media_id)} alt={p.name} className="h-full w-full object-cover" loading="lazy" />
        : <div className="h-full grid place-items-center text-muted-foreground/60"><Package className="h-8 w-8" /></div>}
      {p.category && <span className="absolute top-2 left-2 max-w-[60%] truncate rounded-full bg-black/60 backdrop-blur px-2.5 py-1 text-[10px] font-semibold text-white" data-testid={`product-category-${p.id}`}>{p.category}</span>}
      <div className="absolute top-2 right-2 flex gap-1 opacity-100 sm:opacity-0 group-hover:opacity-100 transition-opacity">
        <button onClick={() => onEdit(p)} data-testid={`product-edit-${p.id}`} className="h-8 w-8 rounded-full bg-black/60 backdrop-blur grid place-items-center text-white hover:bg-black/80"><Pencil className="h-3.5 w-3.5" /></button>
        <button onClick={() => onDelete(p)} data-testid={`product-delete-${p.id}`} className="h-8 w-8 rounded-full bg-black/60 backdrop-blur grid place-items-center text-white hover:text-red-400"><Trash2 className="h-3.5 w-3.5" /></button>
      </div>
    </div>
    <div className="p-3 space-y-2">
      <p className="text-sm font-semibold leading-snug line-clamp-2">{p.name}</p>
      {p.price && <p className="text-sm text-primary font-bold">{p.price}</p>}
      <div className="flex flex-wrap items-center justify-between gap-2"><StockPill p={p} />{p.stock != null && <StockStepper p={p} onSet={onStock} />}</div>
    </div>
  </div>
);

const match = (p, q, cat, view) => `${p.name} ${p.description} ${p.category || ""}`.toLowerCase().includes(q.toLowerCase())
  && (!cat || p.category === cat)
  && (view === "all" || (view === "in" ? ["in", "untracked", "low"].includes(stockState(p)) : stockState(p) === view));

export default function ProductsPanel() {
  const [items, setItems] = useState(null);
  const [editing, setEditing] = useState(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [view, setView] = useState("all");
  const load = () => api.get("/products").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.name}"?`)) return;
    await api.delete(`/products/${p.id}`);
    toast.success("Product deleted");
    load();
  };
  const setStock = async (p, stock) => {
    setItems((xs) => xs.map((x) => (x.id === p.id ? { ...x, stock } : x)));
    try { await api.patch(`/products/${p.id}/stock`, { stock }); } catch (e) { toast.error(errMsg(e)); load(); }
  };
  if (!items) return <div className="p-8 text-muted-foreground/80">Loading…</div>;
  const cats = [...new Set(items.map((p) => p.category).filter(Boolean))].sort();
  if (cat && !cats.includes(cat)) setCat("");
  const list = items.filter((p) => match(p, q, cat, view));

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader eyebrow="Catalog" title="Products" Icon={Package}
          desc={<>When customers ask about a product, the AI sends its photo, name and price automatically. <span className="font-mono text-xs text-muted-foreground/80" data-testid="products-count">{items.length} / 300</span></>}>
          <button onClick={() => setEditing(EMPTY)} data-testid="add-product-btn"
            className="inline-flex items-center gap-2 rounded-full btn-brand px-5 py-2.5 text-sm font-semibold"><Plus className="h-4 w-4" /> Add product</button>
        </PageHeader>
        {items.length > 0 && <SummaryCards items={items} view={view} onView={setView} />}
        {items.length > 0 && (
          <div className="mt-6 flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="relative w-full sm:max-w-xs">
              <Search className="h-4 w-4 absolute left-3 top-2.5 text-muted-foreground/80" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products…" data-testid="products-search-input"
                className="w-full bg-card border border-border rounded-full pl-9 pr-3 py-2 text-sm outline-none focus:border-primary/60" />
            </div>
            <CategoryChips cats={cats} value={cat} onChange={setCat} />
          </div>
        )}
        {items.length === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-border p-12 text-center" data-testid="products-empty">
            <Package className="h-8 w-8 text-muted-foreground/80 mx-auto" />
            <p className="mt-4 font-semibold">No products yet</p>
            <p className="text-sm text-muted-foreground mt-1">Add your first product with a photo. The AI will start showing it to customers.</p>
          </div>
        ) : list.length === 0 ? (
          <p className="mt-10 text-center text-sm text-muted-foreground" data-testid="products-no-match">No products match these filters.</p>
        ) : (
          <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4" data-testid="products-grid">
            {list.map((p) => <ProductCard key={p.id} p={p} onEdit={setEditing} onDelete={remove} onStock={setStock} />)}
          </div>
        )}
      </div>
      {editing && <ProductForm initial={editing.id ? editing : null} cats={cats} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}
