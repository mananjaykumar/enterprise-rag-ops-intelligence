"use client";

import React, { useEffect, useState } from "react";
import { Activity, Zap, Database, Shield, Server, CheckCircle2, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";

interface TelemetryBarProps {
  lastTraceId: string;
  lastLatencyMs: number;
  totalQueriesRun: number;
  authenticatedRole?: string;
  authenticatedTenant?: string;
  isAuthenticated: boolean;
}

export default function TelemetryBar({
  lastTraceId,
  lastLatencyMs,
  totalQueriesRun,
  authenticatedRole,
  authenticatedTenant,
  isAuthenticated,
}: TelemetryBarProps) {
  const [dbStatus, setDbStatus] = useState<string>("checking");
  const [activeModel, setActiveModel] = useState<string>("gemini-embedding-001 (768-d)");
  const [pingMs, setPingMs] = useState<number>(0);

  // Poll health and measure live network round-trip ping every 10 seconds
  useEffect(() => {
    let isMounted = true;

    const measureHealth = async () => {
      const data = await api.checkHealthDetailed();
      if (!isMounted) return;
      setDbStatus(data.database === "connected" ? "connected" : "offline");
      if (data.active_embedding_model && data.active_embedding_model !== "offline") {
        setActiveModel(`${data.active_embedding_model} (768-d)`);
      }
      setPingMs(data.pingMs);
    };

    measureHealth();
    const interval = setInterval(measureHealth, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const isDbConnected = dbStatus === "connected";
  const formattedLatency =
    lastLatencyMs > 0
      ? `${Math.round(lastLatencyMs).toLocaleString()} ms`
      : "0 ms";

  return (
    <footer className="telemetry-bar">
      <div className="aura-container telemetry-inner">
        {/* Left Group: Infrastructure & Partitioning */}
        <div className="telemetry-group">
          {/* Database & Vector Store */}
          <div
            className={`telemetry-badge ${
              isDbConnected ? "telemetry-badge-emerald" : "telemetry-badge-rose"
            }`}
            title="Distributed PostgreSQL 16 + pgvector engine"
          >
            <span
              className="telemetry-pulse-dot"
              style={{
                backgroundColor: isDbConnected
                  ? "var(--brand-emerald)"
                  : "var(--brand-rose)",
                boxShadow: `0 0 8px ${
                  isDbConnected ? "var(--brand-emerald)" : "var(--brand-rose)"
                }`,
              }}
            />
            <span style={{ fontWeight: 600 }}>PostgreSQL 16 + pgvector</span>
            {pingMs > 0 && (
              <span className="telemetry-num" style={{ opacity: 0.7, fontSize: "0.68rem" }}>
                · {pingMs}ms
              </span>
            )}
          </div>

          {/* Active Embedding Model */}
          <div
            className="telemetry-badge telemetry-badge-cyan"
            title="Active enterprise embedding vector pipeline"
          >
            <Server size={12} />
            <span className="telemetry-label">Embedder:</span>
            <span className="telemetry-num">{activeModel}</span>
          </div>

          {/* Tenant & RBAC Partition */}
          <div
            className="telemetry-badge telemetry-badge-indigo"
            title="Multi-tenant authorization boundary"
          >
            <Shield size={12} color={isAuthenticated ? "#818cf8" : "var(--text-muted)"} />
            {isAuthenticated ? (
              <span>
                <span className="telemetry-label">Tenant:</span>{" "}
                <span className="telemetry-num" style={{ color: "#fff" }}>
                  {authenticatedTenant || "default_tenant"}
                </span>{" "}
                <span style={{ opacity: 0.4, margin: "0 2px" }}>·</span>{" "}
                <span
                  className="telemetry-num"
                  style={{ color: "var(--brand-emerald)", fontWeight: 700 }}
                >
                  {authenticatedRole?.toUpperCase() || "USER"}
                </span>
              </span>
            ) : (
              <span style={{ color: "var(--brand-rose)", fontWeight: 500 }}>
                Unauthenticated
              </span>
            )}
          </div>
        </div>

        {/* Right Group: Real-Time Execution Metrics */}
        <div className="telemetry-group">
          {/* Distributed Trace ID */}
          <div
            className="telemetry-badge telemetry-badge-violet"
            title="Distributed x-trace-id of the latest query"
          >
            <Activity size={12} color="#c084fc" />
            <span className="telemetry-label">Trace:</span>
            <span className="telemetry-num" style={{ color: "#e9d5ff" }}>
              {lastTraceId && lastTraceId !== "trace_standby" ? lastTraceId : "Standby"}
            </span>
          </div>

          {/* Query Latency */}
          <div
            className="telemetry-badge telemetry-badge-amber"
            title="Measured end-to-end execution latency"
          >
            <Zap size={12} color="#fbbf24" />
            <span className="telemetry-label">Latency:</span>
            <span className="telemetry-num" style={{ color: "#fef3c7" }}>
              {formattedLatency}
            </span>
          </div>

          {/* Session Queries */}
          <div
            className="telemetry-badge telemetry-badge-emerald"
            title="Total queries executed during active browser session"
          >
            <Database size={12} color="#34d399" />
            <span className="telemetry-label">Queries:</span>
            <span className="telemetry-num" style={{ color: "#a7f3d0" }}>
              {totalQueriesRun}
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
