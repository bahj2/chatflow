import axios from "axios";
import { createContext, useContext, useEffect, useState } from "react";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("rf_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return String(d);
}

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  useEffect(() => {
    // Session ended on the server (teammate removed, plan ended, signed out elsewhere): go back to sign-in with the reason
    const id = api.interceptors.response.use((r) => r, (e) => {
      const url = e?.config?.url || "";
      if (e?.response?.status === 401 && !/^\/auth\/(login|register|google)/.test(url) && e?.config?.headers?.Authorization) {
        // parallel requests may 401 after the token was already cleared: swallow them too (only the first one sets the notice)
        // only the session that was actually rejected is signed out (a late reply from an older session can't end a new one)
        const sent = String(e.config.headers.Authorization).replace(/^Bearer /, "");
        if (localStorage.getItem("rf_token") && localStorage.getItem("rf_token") === sent) {
          localStorage.removeItem("rf_token");
          sessionStorage.setItem("rf_notice", errMsg(e));
          setUser(false);
        }
        return new Promise(() => {}); // leaving the dashboard: let pending screens wait quietly instead of erroring
      }
      return Promise.reject(e);
    });
    return () => api.interceptors.response.eject(id);
  }, []);

  useEffect(() => {
    // Returning from Google: AuthCallback exchanges session_id first
    if (window.location.hash?.includes("session_id=")) return;
    if (!localStorage.getItem("rf_token")) return setUser(false);
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(false));
  }, []);

  const save = (data) => {
    localStorage.setItem("rf_token", data.token);
    setUser(data.user);
    return data;
  };
  const login = async (email, password) => save((await api.post("/auth/login", { email, password })).data);
  const register = async (body) => save((await api.post("/auth/register", body)).data);
  const loginGoogle = async (session_id) => save((await api.post("/auth/google", { session_id })).data);
  const loginFacebook = async (code) => save((await api.post("/auth/facebook/finish", { code })).data);
  const failGoogle = () => setUser(false);
  const logout = () => {
    localStorage.removeItem("rf_token");
    setUser(false);
  };
  return <AuthCtx.Provider value={{ user, setUser, setSession: save, login, register, loginGoogle, loginFacebook, failGoogle, logout }}>{children}</AuthCtx.Provider>;
};

export const useAuth = () => useContext(AuthCtx);
