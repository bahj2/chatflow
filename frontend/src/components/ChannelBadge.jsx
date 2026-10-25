import { Send, Facebook } from "lucide-react";

const MAP = {
  telegram: { label: "Telegram", color: "#229ED9", Icon: Send },
  messenger: { label: "Messenger", color: "#0084FF", Icon: Facebook },
};

export const ChannelBadge = ({ channel, compact = false }) => {
  const c = MAP[channel] || MAP.telegram;
  return (
    <span
      data-testid={`channel-badge-${channel}`}
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
      style={{ color: c.color, background: `${c.color}1f`, border: `1px solid ${c.color}40` }}
    >
      <c.Icon className="h-3 w-3" />
      {!compact && c.label}
    </span>
  );
};
