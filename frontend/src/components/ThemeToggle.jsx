import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

export const ThemeToggle = ({ className = "", testid = "theme-toggle" }) => {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button type="button" onClick={toggle} data-testid={testid} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className={`relative grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:text-foreground hover:bg-muted ${className}`}>
      <Sun className={`h-4 w-4 absolute transition-[transform,opacity] duration-300 ${dark ? "opacity-0 rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"}`} />
      <Moon className={`h-4 w-4 absolute transition-[transform,opacity] duration-300 ${dark ? "opacity-100 rotate-0 scale-100" : "opacity-0 -rotate-90 scale-50"}`} />
    </button>
  );
};
