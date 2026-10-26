import { createContext, useCallback, useContext, useState } from "react";

const KEY = "rf_theme";
const ThemeCtx = createContext({ theme: "dark", toggle: () => {} });

const read = () => {
  try { return localStorage.getItem(KEY) || "dark"; } catch { return "dark"; }
};

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(read);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try { localStorage.setItem(KEY, next); } catch { /* private mode */ }
      return next;
    });
  }, []);
  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
};

export const useTheme = () => useContext(ThemeCtx);
