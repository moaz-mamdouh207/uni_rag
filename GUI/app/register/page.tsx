"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen } from "lucide-react";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ThemeToggle from "@/components/ThemeToggle";

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await auth.register({ full_name: fullName, email, password });
      await login(email, password);
      router.replace("/chat");
    } catch {
      setError("Registration failed. The email may already be in use.");
    } finally {
      setLoading(false);
    }
  };

  const ready = !!fullName.trim() && !!email.trim() && !!password;

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", display: "flex", flexDirection: "column" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1rem 1.5rem", borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <div style={{ width: 32, height: 32, background: "var(--accent-glow)", border: "1px solid var(--border)", borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <BookOpen size={16} color="var(--accent)" />
          </div>
          <span style={{ fontWeight: 600, fontSize: "0.95rem", letterSpacing: "-0.02em" }}>UniRAG</span>
        </div>
        <ThemeToggle />
      </header>

      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem 1rem" }}>
        <div className="fade-in" style={{ width: "100%", maxWidth: 380, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, padding: "2rem" }}>
          <h1 style={{ margin: "0 0 0.3rem", fontSize: "1.3rem", fontWeight: 600, color: "var(--text)" }}>Create account</h1>
          <p style={{ margin: "0 0 1.5rem", fontSize: "0.85rem", color: "var(--text-3)" }}>Start using UniRAG today</p>

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-2)", marginBottom: "0.4rem", letterSpacing: "0.04em", textTransform: "uppercase" }}>Full name</label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="Jane Smith"
                style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 9, padding: "0.65rem 0.9rem", color: "var(--text)", fontSize: "0.9rem", outline: "none", fontFamily: "inherit", boxSizing: "border-box" }}
                onFocus={e => (e.target.style.borderColor = "var(--accent)")}
                onBlur={e => (e.target.style.borderColor = "var(--border)")}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-2)", marginBottom: "0.4rem", letterSpacing: "0.04em", textTransform: "uppercase" }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@university.edu"
                style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 9, padding: "0.65rem 0.9rem", color: "var(--text)", fontSize: "0.9rem", outline: "none", fontFamily: "inherit", boxSizing: "border-box" }}
                onFocus={e => (e.target.style.borderColor = "var(--accent)")}
                onBlur={e => (e.target.style.borderColor = "var(--border)")}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-2)", marginBottom: "0.4rem", letterSpacing: "0.04em", textTransform: "uppercase" }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                onKeyDown={e => e.key === "Enter" && handleSubmit(e as unknown as React.FormEvent)}
                style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 9, padding: "0.65rem 0.9rem", color: "var(--text)", fontSize: "0.9rem", outline: "none", fontFamily: "inherit", boxSizing: "border-box" }}
                onFocus={e => (e.target.style.borderColor = "var(--accent)")}
                onBlur={e => (e.target.style.borderColor = "var(--border)")}
              />
            </div>

            {error && (
              <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--danger)", background: "rgba(192,57,43,0.08)", border: "1px solid rgba(192,57,43,0.2)", borderRadius: 8, padding: "0.5rem 0.75rem" }}>
                {error}
              </p>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading || !ready}
              style={{ width: "100%", background: !ready ? "var(--border)" : "var(--accent)", border: "none", borderRadius: 9, padding: "0.7rem", fontSize: "0.92rem", fontWeight: 500, cursor: !ready ? "not-allowed" : "pointer", color: !ready ? "var(--text-3)" : "#fff", fontFamily: "inherit", transition: "background 0.15s" }}
            >
              {loading ? "Creating account…" : "Create account"}
            </button>

            <p style={{ margin: 0, textAlign: "center", fontSize: "0.82rem", color: "var(--text-3)" }}>
              Already have an account?{" "}
              <a href="/login" style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 500 }}>Sign in</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}