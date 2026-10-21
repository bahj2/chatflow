import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Embed from "@/pages/Embed";
import AuthCallback from "@/pages/AuthCallback";

const Protected = ({ children }) => {
  const { user } = useAuth();
  if (user === null) return <div className="min-h-screen grid place-items-center text-slate-400">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

function AppRoutes() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/embed" element={<Embed />} />
      <Route path="/dashboard/*" element={<Protected><Dashboard /></Protected>} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
      <Toaster theme="dark" position="top-center" />
    </AuthProvider>
  );
}

export default App;
