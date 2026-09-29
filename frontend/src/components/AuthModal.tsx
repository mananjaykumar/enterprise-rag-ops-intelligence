"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  Key,
  LogOut,
  X,
  AlertCircle,
  CheckCircle,
  Lock,
  UserPlus,
  LogIn,
  User,
  Building,
} from "lucide-react";
import { api, DecodedToken } from "@/lib/api";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthChange: () => void;
}

export default function AuthModal({ isOpen, onClose, onAuthChange }: AuthModalProps) {
  const [activeTab, setActiveTab] = useState<"login" | "register">("login");
  const [decodedUser, setDecodedUser] = useState<DecodedToken | null>(null);
  const [currentToken, setCurrentToken] = useState<string | null>(null);

  // Sign In Form States
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginTenantId, setLoginTenantId] = useState("default_tenant");

  // Register Form States
  const [regFullName, setRegFullName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regRole, setRegRole] = useState<"admin" | "manager" | "analyst">("analyst");
  const [regTenantId, setRegTenantId] = useState("default_tenant");

  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const tok = api.getToken();
    setCurrentToken(tok);
    setDecodedUser(api.getDecodedUser());
    setStatusMsg(null);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail.trim() || !loginPassword.trim()) {
      setStatusMsg({ type: "error", text: "Please enter your email and password." });
      return;
    }

    setLoading(true);
    setStatusMsg(null);

    try {
      await api.login(loginEmail.trim(), loginPassword, loginTenantId.trim() || "default_tenant");
      setCurrentToken(api.getToken());
      setDecodedUser(api.getDecodedUser());
      setStatusMsg({ type: "success", text: "Successfully authenticated!" });
      onAuthChange();
      setTimeout(() => {
        onClose();
      }, 800);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication failed";
      setStatusMsg({ type: "error", text: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regFullName.trim() || !regEmail.trim() || !regPassword.trim()) {
      setStatusMsg({ type: "error", text: "Please fill in all required fields." });
      return;
    }

    setLoading(true);
    setStatusMsg(null);

    try {
      // 1. Call register
      await api.register(
        regEmail.trim(),
        regPassword,
        regFullName.trim(),
        regRole,
        regTenantId.trim() || "default_tenant"
      );
      // 2. Automatically log in the newly registered user
      await api.login(regEmail.trim(), regPassword, regTenantId.trim() || "default_tenant");
      setCurrentToken(api.getToken());
      setDecodedUser(api.getDecodedUser());
      setStatusMsg({ type: "success", text: "Account created and authenticated successfully!" });
      onAuthChange();
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      setStatusMsg({ type: "error", text: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    api.logout();
    setCurrentToken(null);
    setDecodedUser(null);
    setStatusMsg({ type: "success", text: "Signed out successfully." });
    onAuthChange();
  };

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="modal-container auth-modal-box" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: "rgba(99, 102, 241, 0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--brand-indigo)",
              }}
            >
              <Shield size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0 }}>
                Enterprise Access Control
              </h2>
              <div style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                Strict Tenant Isolation & Role-Based Access Control (RBAC)
              </div>
            </div>
          </div>

          <button className="modal-close-btn" onClick={onClose} title="Close modal">
            <X size={18} />
          </button>
        </div>

        {/* Current Active Session Card (If Logged In) */}
        {currentToken && decodedUser && (
          <div
            style={{
              margin: "16px 24px 0",
              padding: "14px 18px",
              background: "rgba(16, 185, 129, 0.08)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  background: "rgba(16, 185, 129, 0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--brand-emerald)",
                }}
              >
                <User size={16} />
              </div>
              <div>
                <div style={{ fontSize: "0.86rem", fontWeight: 600, color: "#fff" }}>
                  {decodedUser.email}
                </div>
                <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
                  Role: <strong style={{ color: "var(--brand-emerald)" }}>{decodedUser.role?.toUpperCase()}</strong> · Tenant: <strong style={{ color: "var(--brand-cyan)" }}>{decodedUser.tenant_id}</strong>
                </div>
              </div>
            </div>

            <button
              onClick={handleLogout}
              className="nav-tab-btn"
              style={{
                padding: "6px 12px",
                fontSize: "0.78rem",
                color: "var(--brand-rose)",
                borderColor: "rgba(244, 63, 94, 0.3)",
              }}
            >
              <LogOut size={13} />
              Sign Out
            </button>
          </div>
        )}

        {/* Tab Navigation */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--border-subtle)",
            padding: "0 24px",
            marginTop: "16px",
          }}
        >
          <button
            onClick={() => {
              setActiveTab("login");
              setStatusMsg(null);
            }}
            style={{
              padding: "10px 18px",
              fontSize: "0.88rem",
              fontWeight: 600,
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "login" ? "2px solid var(--brand-indigo)" : "2px solid transparent",
              color: activeTab === "login" ? "#fff" : "var(--text-muted)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s",
            }}
          >
            <LogIn size={15} />
            Sign In
          </button>
          <button
            onClick={() => {
              setActiveTab("register");
              setStatusMsg(null);
            }}
            style={{
              padding: "10px 18px",
              fontSize: "0.88rem",
              fontWeight: 600,
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "register" ? "2px solid var(--brand-indigo)" : "2px solid transparent",
              color: activeTab === "register" ? "#fff" : "var(--text-muted)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              transition: "all 0.2s",
            }}
          >
            <UserPlus size={15} />
            Register Account
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "20px 24px 24px", overflowY: "auto", flex: 1 }}>
          {/* Status Message */}
          {statusMsg && (
            <div
              style={{
                padding: "10px 14px",
                marginBottom: "16px",
                borderRadius: "8px",
                fontSize: "0.82rem",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background:
                  statusMsg.type === "success"
                    ? "rgba(16, 185, 129, 0.12)"
                    : "rgba(244, 63, 94, 0.12)",
                border:
                  statusMsg.type === "success"
                    ? "1px solid rgba(16, 185, 129, 0.3)"
                    : "1px solid rgba(244, 63, 94, 0.3)",
                color:
                  statusMsg.type === "success"
                    ? "var(--brand-emerald)"
                    : "var(--brand-rose)",
              }}
            >
              {statusMsg.type === "success" ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              <span>{statusMsg.text}</span>
            </div>
          )}

          {/* SIGN IN TAB */}
          {activeTab === "login" && (
            <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                  Corporate Email Address
                </label>
                <input
                  type="email"
                  className="omnibox-textarea"
                  style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                  placeholder="e.g. your.name@enterprise.com"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                  Account Password
                </label>
                <input
                  type="password"
                  className="omnibox-textarea"
                  style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                  placeholder="••••••••••••"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                  Enterprise Tenant ID
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Building size={16} color="var(--text-muted)" />
                  <input
                    type="text"
                    className="omnibox-textarea"
                    style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                    placeholder="default_tenant"
                    value={loginTenantId}
                    onChange={(e) => setLoginTenantId(e.target.value)}
                  />
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "4px" }}>
                  Documents and SQL databases are isolated per tenant boundary.
                </div>
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={loading || !loginEmail.trim() || !loginPassword.trim()}
                style={{ width: "100%", justifyContent: "center", marginTop: "8px" }}
              >
                <Lock size={15} />
                {loading ? "Authenticating..." : "Sign In to Platform"}
              </button>
            </form>
          )}

          {/* REGISTER TAB */}
          {activeTab === "register" && (
            <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                  Full Legal Name
                </label>
                <input
                  type="text"
                  className="omnibox-textarea"
                  style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                  placeholder="e.g. Sarah Connor"
                  value={regFullName}
                  onChange={(e) => setRegFullName(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                  Corporate Email Address
                </label>
                <input
                  type="email"
                  className="omnibox-textarea"
                  style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                  placeholder="e.g. sarah.connor@cyberdyne.com"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                  Secure Password
                </label>
                <input
                  type="password"
                  className="omnibox-textarea"
                  style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                  placeholder="Minimum 8 characters"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                    Platform Role (RBAC)
                  </label>
                  <select
                    className="persona-select"
                    style={{ width: "100%", height: "42px" }}
                    value={regRole}
                    onChange={(e) => setRegRole(e.target.value as "admin" | "manager" | "analyst")}
                  >
                    <option value="analyst">Analyst (Standard Read)</option>
                    <option value="manager">Manager (Upload & Review)</option>
                    <option value="admin">Administrator (Full Access)</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                    Tenant Domain
                  </label>
                  <input
                    type="text"
                    className="omnibox-textarea"
                    style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                    placeholder="default_tenant"
                    value={regTenantId}
                    onChange={(e) => setRegTenantId(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={loading || !regFullName.trim() || !regEmail.trim() || !regPassword.trim()}
                style={{
                  width: "100%",
                  justifyContent: "center",
                  marginTop: "8px",
                  background: "linear-gradient(135deg, var(--brand-emerald) 0%, #059669 100%)",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.35)",
                }}
              >
                <UserPlus size={15} />
                {loading ? "Creating Account..." : "Register & Authenticate"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
