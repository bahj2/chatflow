import { Send, ArrowLeft, MoreVertical, CheckCheck } from "lucide-react";

const LATTE = "https://images.unsplash.com/photo-1671759545218-831c32bfe92d?crop=entropy&cs=srgb&fm=jpg&q=80&w=600";

const Time = ({ t, read }) => (
  <span className="float-right ml-3 mt-1.5 text-[10px] text-slate-400/80 inline-flex items-center gap-0.5">{t}{read && <CheckCheck className="h-3 w-3 text-sky-300" />}</span>
);

const Me = ({ children, t, d }) => (
  <div className="flex justify-end tg-pop" style={{ animationDelay: d }}>
    <div className="max-w-[78%] rounded-2xl rounded-br-md bg-[#2B5278] px-3 py-2 text-[13px] leading-relaxed text-white">{children}<Time t={t} read /></div>
  </div>
);

const Bot = ({ children, t, d, photo, caption, width = "max-w-[80%]", imgClass = "" }) => (
  <div className="flex tg-pop" style={{ animationDelay: d }}>
    <div className={`${width} rounded-2xl rounded-bl-md bg-[#182533] overflow-hidden text-[13px] leading-relaxed text-slate-100`}>
      {photo && <img src={photo} alt={caption || ""} className={`w-full object-cover ${imgClass}`} loading="lazy" />}
      <div className="px-3 py-2">{caption && <p className="text-[12px] text-slate-300">{caption}</p>}{children}<Time t={t} /></div>
    </div>
  </div>
);

export const TelegramDemo = ({ className = "" }) => (
  <div className={`rounded-[28px] border border-white/10 bg-[#0E1621] shadow-2xl overflow-hidden flex flex-col ${className}`} data-testid="telegram-demo">
    <div className="flex items-center gap-3 bg-[#17212B] px-4 py-3 border-b border-black/30">
      <ArrowLeft className="h-4 w-4 text-slate-400" />
      <span className="h-9 w-9 rounded-full bg-gradient-to-br from-amber-400 to-orange-600 grid place-items-center text-xs font-bold text-white">SC</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white truncate">Sunrise Coffee</p>
        <p className="text-[11px] text-sky-300">bot · replies instantly</p>
      </div>
      <MoreVertical className="h-4 w-4 text-slate-400" />
    </div>
    <div className="flex-1 space-y-2.5 px-3 py-4 overflow-hidden font-[Noto_Sans_Khmer,ui-sans-serif]"
      style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.035) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
      <Me t="09:41" d="0.2s">បងមានកាហ្វេទឹកដោះគោត្រជាក់ទេ?</Me>
      <Bot t="09:41" d="0.7s" photo={LATTE} caption="Iced Palm Sugar Latte — 2.5$" width="w-[58%]" imgClass="h-32" />
      <Bot t="09:41" d="1.1s">មានបង! Iced Palm Sugar Latte តម្លៃ 2.5$ មួយកែវ។ បងចង់បានប៉ុន្មានកែវ?</Bot>
      <Me t="09:42" d="1.6s">យក ២ កែវ</Me>
      <Bot t="09:42" d="2.1s" photo="/landing/khqr-demo.png" caption="Bakong KHQR · $5.00 · valid 10 min" width="w-[42%]" />
      <Bot t="09:43" d="2.7s">បានទទួលការទូទាត់ ✅ សូមអរគុណ! ការកម្ម៉ង់ RF-7C21A9E4 · $5.00</Bot>
    </div>
    <div className="flex items-center gap-2 bg-[#17212B] px-4 py-3">
      <p className="flex-1 text-[13px] text-slate-500">Message</p>
      <Send className="h-4 w-4 text-sky-400" />
    </div>
  </div>
);
