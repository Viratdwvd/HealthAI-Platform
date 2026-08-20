"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("demo_user");
  const [password, setPassword] = useState("demo");
  const [tenantId, setTenantId] = useState("tenant-demo");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const resp = await fetch("http://localhost:8000/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, tenant_id: tenantId }),
      });
      const data = await resp.json();
      if (data.access_token) {
          localStorage.setItem("hai_token", data.access_token);
          document.cookie = `hai_token=${data.access_token}; path=/; SameSite=Lax`;
          router.push("/");
      } else {
        setError("Login failed");
      }
    } catch {
      setError("Cannot reach server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a" }}>
      <div style={{ background: "#1e293b", padding: "2rem", borderRadius: "12px", width: "340px" }}>
        <h1 style={{ color: "#f1f5f9", marginBottom: "1.5rem", fontSize: "20px" }}>HealthAI Login</h1>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ color: "#94a3b8", fontSize: "13px", display: "block" }}>Tenant ID</label>
            <input value={tenantId} onChange={e => setTenantId(e.target.value)} style={{ width: "100%", padding: "8px", marginTop: "4px", background: "#0f172a", border: "1px solid #334155", color: "#f1f5f9", borderRadius: "6px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ color: "#94a3b8", fontSize: "13px", display: "block" }}>Username</label>
            <input value={username} onChange={e => setUsername(e.target.value)} style={{ width: "100%", padding: "8px", marginTop: "4px", background: "#0f172a", border: "1px solid #334155", color: "#f1f5f9", borderRadius: "6px", boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ color: "#94a3b8", fontSize: "13px", display: "block" }}>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ width: "100%", padding: "8px", marginTop: "4px", background: "#0f172a", border: "1px solid #334155", color: "#f1f5f9", borderRadius: "6px", boxSizing: "border-box" }} />
          </div>
          {error && <p style={{ color: "#f87171", fontSize: "13px", marginBottom: "1rem" }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "10px", background: "#1189eb", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "14px" }}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p style={{ color: "#475569", fontSize: "11px", marginTop: "1rem", textAlign: "center" }}>demo_user / demo / tenant-demo</p>
      </div>
    </div>
  );
}