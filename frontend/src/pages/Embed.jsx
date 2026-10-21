import { ChatPanel } from "@/components/ChatWidget";

export default function Embed() {
  const params = new URLSearchParams(window.location.search);
  const site = params.get("site");
  const bid = params.get("b") || "default";
  return (
    <div className="h-screen w-screen bg-[#0F1522]" data-testid="embed-page">
      <ChatPanel businessId={bid} className="h-full !rounded-none !border-0" visitorName={site ? `Visitor from ${site}` : "Website visitor"} />
    </div>
  );
}
