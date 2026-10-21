import { ChatPanel } from "@/components/ChatWidget";

export default function Embed() {
  const site = new URLSearchParams(window.location.search).get("site");
  return (
    <div className="h-screen w-screen bg-[#0F1522]" data-testid="embed-page">
      <ChatPanel className="h-full !rounded-none !border-0" visitorName={site ? `Visitor from ${site}` : "Website visitor"} />
    </div>
  );
}
