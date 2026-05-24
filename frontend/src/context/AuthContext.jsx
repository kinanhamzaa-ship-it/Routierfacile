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
      return { ok: true };
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail && typeof detail === "object" && detail.code === "email_not_verified") {
        setError(detail.message);
        return { ok: false, code: "email_not_verified", email: detail.email || email };
      }
      setError(formatApiError(detail) || e.message);
      return { ok: false };
    }
  }, []);

  const register = useCallback(async (email, password, name) => {
    setError("");
    try {
      const { data } = await api.post("/auth/register", { email, password, name });
      // Email-verification flow: we never auto-login on register. The user
      // receives an email and must click the link before /auth/login succeeds.
      return { ok: true, email: data.email, message: data.message };
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return { ok: false };
    }
  }, []);

  const resendVerification = useCallback(async (email) => {
    try {
      const { data } = await api.post("/auth/resend-verification", { email });
      return { ok: true, message: data?.message };
    } catch (e) {
      return { ok: false, message: formatApiError(e.response?.data?.detail) || e.message };
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
    () => ({ user, login, register, logout, resendVerification, error, setError }),
    [user, login, register, logout, resendVerification, error]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
