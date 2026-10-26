import { useEffect, useRef, useState } from "react";
import { Plus, Pencil, Trash2, ImagePlus, Loader2, Package, Search } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const EMPTY = { name: "", price: "", description: "", image_media_id: "" };

const ProductForm = ({ initial, onClose, onSaved }) => {
  const [f, setF] = useState(initial || EMPTY);
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
      const body = { name: f.name, price: f.price, description: f.description, image_media_id: f.image_media_id };
      if (initial?.id) await api.put(`/products/${initial.id}`, body); else await api.post("/products", body);
      toast.success("Product saved");
      onSaved();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-card border-border max-w-lg" data-testid="product-dialog">
        <DialogHeader><DialogTitle className="font-display">{initial?.id ? "Edit product" : "Add product"}</DialogTitle></DialogHeader>
        <div className="grid sm:grid-cols-[160px_1fr] gap-4">
          <button type="button" onClick={() => fileRef.current?.click()} data-testid="product-image-btn"
            className="h-40 rounded-xl border border-dashed border-foreground/15 bg-muted/50 grid place-items-center overflow-hidden hover:border-emerald-500/50 transition-colors">
            {uploading ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              : f.image_media_id ? <img src={mediaUrl(f.image_media_id)} alt="" className="h-full w-full object-cover" data-testid="product-image-preview" />
              : <span className="text-xs text-muted-foreground flex flex-col items-center gap-2"><ImagePlus className="h-6 w-6" />Add photo</span>}
          </button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" data-testid="product-image-input" onChange={(e) => upload(e.target.files?.[0])} />
          <div className="space-y-3">
            <Input placeholder="Product name" value={f.name} onChange={set("name")} data-testid="product-name-input" />
            <Input placeholder="Price, e.g. $25 or 100,000 ៛" value={f.price} onChange={set("price")} data-testid="product-price-input" />
            <Textarea rows={4} placeholder="Description: size, colour, material… (helps the AI pick the right product)" value={f.description} onChange={set("description")} data-testid="product-description-input" />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="rounded-full px-5 py-2 text-sm text-foreground/80 hover:bg-muted/60" data-testid="product-cancel-btn">Cancel</button>
          <button onClick={save} disabled={saving || uploading} data-testid="product-save-btn"
            className="rounded-full btn-brand px-5 py-2 text-sm font-semibold disabled:opacity-60">{saving ? "Saving…" : "Save product"}</button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default function ProductsPanel() {
  const [items, setItems] = useState(null);
  const [editing, setEditing] = useState(null);
  const [q, setQ] = useState("");
  const load = () => api.get("/products").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  const remove = async (p) => {
    if (!window.confirm(`Delete "${p.name}"?`)) return;
    await api.delete(`/products/${p.id}`);
    toast.success("Product deleted");
    load();
  };
  if (!items) return <div className="p-8 text-muted-foreground/80">Loading…</div>;
  const list = items.filter((p) => `${p.name} ${p.description}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl font-bold">Products</h1>
            <p className="text-sm text-muted-foreground mt-1">When customers ask about a product, the AI sends its photo, name and price automatically. <span className="text-muted-foreground/80" data-testid="products-count">{items.length} / 300</span></p>
          </div>
          <button onClick={() => setEditing(EMPTY)} data-testid="add-product-btn"
            className="inline-flex items-center gap-2 rounded-full btn-brand px-5 py-2.5 text-sm font-semibold"><Plus className="h-4 w-4" /> Add product</button>
        </div>
        {items.length > 0 && (
          <div className="relative max-w-sm mt-6">
            <Search className="h-4 w-4 absolute left-3 top-2.5 text-muted-foreground/80" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products…" data-testid="products-search-input"
              className="w-full bg-muted/50 border border-border rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-emerald-500/60" />
          </div>
        )}
        {items.length === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-border p-12 text-center" data-testid="products-empty">
            <Package className="h-8 w-8 text-muted-foreground/80 mx-auto" />
            <p className="mt-4 font-semibold">No products yet</p>
            <p className="text-sm text-muted-foreground mt-1">Add your first product with a photo — the AI will start showing it to customers.</p>
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4" data-testid="products-grid">
            {list.map((p) => (
              <div key={p.id} className="group rounded-xl overflow-hidden border border-border bg-card" data-testid={`product-card-${p.id}`}>
                <div className="aspect-square bg-muted/50 relative">
                  {p.image_media_id ? <img src={mediaUrl(p.image_media_id)} alt={p.name} className="h-full w-full object-cover" loading="lazy" />
                    : <div className="h-full grid place-items-center text-muted-foreground/60"><Package className="h-8 w-8" /></div>}
                  <div className="absolute top-2 right-2 flex gap-1 opacity-100 sm:opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => setEditing(p)} data-testid={`product-edit-${p.id}`} className="h-8 w-8 rounded-full bg-black/60 backdrop-blur grid place-items-center hover:bg-black/80"><Pencil className="h-3.5 w-3.5" /></button>
                    <button onClick={() => remove(p)} data-testid={`product-delete-${p.id}`} className="h-8 w-8 rounded-full bg-black/60 backdrop-blur grid place-items-center hover:text-red-600 dark:hover:text-red-400"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
                <div className="p-3">
                  <p className="text-sm font-semibold leading-snug line-clamp-2">{p.name}</p>
                  {p.price && <p className="text-sm text-emerald-600 dark:text-emerald-400 font-semibold mt-1">{p.price}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {editing && <ProductForm initial={editing.id ? editing : null} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}
