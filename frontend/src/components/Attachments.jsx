import { ImageOff } from "lucide-react";
import { BACKEND_URL } from "@/lib/auth";

export const mediaUrl = (id) => `${BACKEND_URL}/api/media/${id}`;

export const AudioAtt = ({ a, testid }) => (
  <audio controls preload="metadata" src={a.url || mediaUrl(a.media_id)} className="h-9 w-56 max-w-full" data-testid={testid} />
);

export const ProductCard = ({ p, testid }) => (
  <div className="min-w-0 rounded-xl overflow-hidden border border-white/10 bg-slate-900" data-testid={testid}>
    {p.media_id ? <img src={mediaUrl(p.media_id)} alt={p.name} className="aspect-square w-full object-cover" loading="lazy" />
      : <div className="aspect-square grid place-items-center text-slate-600"><ImageOff className="h-6 w-6" /></div>}
    <div className="px-3 py-2">
      <p className="text-xs font-semibold leading-snug line-clamp-2">{p.name}</p>
      {p.price && <p className="text-xs text-emerald-400 font-semibold mt-0.5">{p.price}</p>}
    </div>
  </div>
);

export const Attachments = ({ atts = [], prefix }) => {
  const audio = atts.filter((a) => a.type === "audio");
  const products = atts.filter((a) => a.type === "product");
  if (!audio.length && !products.length) return null;
  return (
    <div className="space-y-2">
      {audio.map((a, i) => <AudioAtt key={i} a={a} testid={`${prefix}-audio`} />)}
      {products.length > 0 && (
        <div className="grid grid-cols-2 gap-2 w-[22rem] max-w-full">{products.map((p) => <ProductCard key={p.product_id} p={p} testid={`${prefix}-product`} />)}</div>
      )}
    </div>
  );
};
