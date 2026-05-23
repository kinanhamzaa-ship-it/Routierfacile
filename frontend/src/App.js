import { useEffect } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import NewEntry from "./pages/NewEntry";
import EditEntry from "./pages/EditEntry";
import History from "./pages/History";
import Monthly from "./pages/Monthly";
import BottomNav from "./components/BottomNav";
import { Toaster } from "./components/ui/sonner";

function Protected({ children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (user === null)
    return (
      <div className="rf-app-min-h-screen flex items-center justify-center text-rf-muted text-sm">
        Chargement…
      </div>
    );
  if (!user) return <Navigate to="/login" state={{ from: loc }} replace />;
  return children;
}

function Shell({ children }) {
  return (
    <div className="rf-app-min-h pb-28 rf-grain rf-safe-top">
      <div className="max-w-md mx-auto relative z-10 px-0">{children}</div>
      <BottomNav />
    </div>
  );
}

function Router() {
  useEffect(() => {
    document.documentElement.classList.add("dark");
  }, []);
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <Protected>
            <Shell><Dashboard /></Shell>
          </Protected>
        }
      />
      <Route
        path="/new"
        element={
          <Protected>
            <Shell><NewEntry /></Shell>
          </Protected>
        }
      />
      <Route
        path="/edit/:id"
        element={
          <Protected>
            <Shell><EditEntry /></Shell>
          </Protected>
        }
      />
      <Route
        path="/history"
        element={
          <Protected>
            <Shell><History /></Shell>
          </Protected>
        }
      />
      <Route
        path="/monthly"
        element={
          <Protected>
            <Shell><Monthly /></Shell>
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Router />
          <Toaster theme="dark" position="top-center" />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}
