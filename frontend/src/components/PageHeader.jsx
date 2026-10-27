export const PageHeader = ({ eyebrow, title, desc, Icon, children, className = "" }) => (
  <header className={`rise flex flex-wrap items-end justify-between gap-4 pb-6 border-b border-border/70 ${className}`}>
    <div className="min-w-0">
      {eyebrow && <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">{eyebrow}</p>}
      <h1 className="mt-1.5 font-display text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-3">
        {Icon && <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></span>}
        {title}
      </h1>
      {desc && <p className="text-sm text-muted-foreground mt-2 max-w-2xl leading-relaxed">{desc}</p>}
    </div>
    {children && <div className="flex flex-wrap items-center gap-3">{children}</div>}
  </header>
);

export const TH = "px-5 py-3 text-[11px] font-mono font-medium uppercase tracking-wider text-muted-foreground";
