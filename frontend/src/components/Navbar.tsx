"use client";

import React from "react";
import {
  Brain,
  Sparkles,
  UploadCloud,
  User,
  LogOut,
  LogIn,
  Shield,
} from "lucide-react";
import { HealthStatus } from "@/lib/api";

export type ActiveTab = "chat" | "docs";

interface NavbarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  health: HealthStatus;
  onOpenAuth: () => void;
  onLogout: () => void;
  isAuthenticated: boolean;
  currentUserEmail?: string;
  currentUserRole?: string;
  currentUserTenant?: string;
}

export default function Navbar({
  activeTab,
  setActiveTab,
  health,
  onOpenAuth,
  onLogout,
  isAuthenticated,
  currentUserEmail,
  currentUserRole,
  currentUserTenant,
}: NavbarProps) {
  const isHealthy = health.status === "healthy";

  return (
    <header className="navbar">
      <div className="aura-container navbar-inner">
        {/* Brand / Logo */}
        <div className="brand-wrapper" onClick={() => setActiveTab("chat")} style={{ cursor: "pointer" }}>
          <div className="brand-icon-box">
            <Brain size={22} />
          </div>
          <div>
            <div className="brand-title">Enterprise RAG & Operations</div>
            <div className="brand-subtitle">Intelligence Platform</div>
          </div>
        </div>

        {/* Center Nav Tabs */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab-btn ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            <Sparkles size={15} />
            Enterprise Intelligence
          </button>
          <button
            className={`nav-tab-btn ${activeTab === "docs" ? "active" : ""}`}
            onClick={() => setActiveTab("docs")}
          >
            <UploadCloud size={15} />
            Documents
          </button>
        </nav>

        {/* Right Controls: Single User Auth & Health */}
        <div className="nav-controls" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* Health Indicator */}
          <div
            className="health-badge"
            title={`FastAPI & PostgreSQL + pgvector status: ${health.status}`}
          >
            <span
              className="health-dot"
              style={{
                backgroundColor: isHealthy ? "var(--brand-emerald)" : "var(--brand-rose)",
                boxShadow: `0 0 8px ${isHealthy ? "var(--brand-emerald)" : "var(--brand-rose)"}`,
              }}
            />
            {isHealthy ? "System Ready" : "Offline"}
          </div>

          {/* Authenticated User Status or Sign In Button */}
          {isAuthenticated ? (
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                onClick={onOpenAuth}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "7px",
                  padding: "5px 12px",
                  background: "rgba(99, 102, 241, 0.12)",
                  border: "1px solid rgba(99, 102, 241, 0.25)",
                  borderRadius: "20px",
                  fontSize: "0.78rem",
                  color: "#fff",
                  cursor: "pointer",
                }}
                title="Click to view session details or manage access"
              >
                <User size={13} color="var(--brand-indigo)" />
                <span style={{ maxWidth: "140px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {currentUserEmail}
                </span>
                <span
                  style={{
                    fontSize: "0.68rem",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: "rgba(16, 185, 129, 0.2)",
                    color: "var(--brand-emerald)",
                    fontWeight: 700,
                    textTransform: "uppercase",
                  }}
                >
                  {currentUserRole || "USER"}
                </span>
              </div>

              <button
                className="nav-tab-btn"
                onClick={onLogout}
                style={{
                  padding: "6px 10px",
                  fontSize: "0.76rem",
                  color: "var(--text-muted)",
                }}
                title="Sign out of platform"
              >
                <LogOut size={13} />
                Sign Out
              </button>
            </div>
          ) : (
            <button
              className="btn-primary"
              onClick={onOpenAuth}
              style={{
                padding: "7px 16px",
                fontSize: "0.82rem",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
              title="Sign in or register an account"
            >
              <LogIn size={14} />
              <span>Sign In / Register</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
