import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, { formatApiError } from "../lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, object = authed
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("rf_token");
    if (!token) {
      setUser(false);
      return;
    }
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem("rf_token");
        setUser(false);
      });
  }, []);

  const login = useCallback(async (email, password) => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("rf_token", data.token);
      setUser(data.user);
      return true;
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return false;
    }
  }, []);

  const register = useCallback(async (email, password, name) => {
    setError("");
    try {
      const { data } = await api.post("/auth/register", { email, password, name });
      localStorage.setItem("rf_token", data.token);
      setUser(data.user);
      return true;
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.error("Logout API call failed:", err);
    }
    localStorage.removeItem("rf_token");
    setUser(false);
  }, []);

  const value = useMemo(
    () => ({ user, login, register, logout, error, setError }),
    [user, login, register, logout, error]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
