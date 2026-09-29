"use client";

import React, { useState } from "react";
import {
  Database,
  ShieldCheck,
  Play,
  Copy,
  Check,
  Table,
  Cpu,
  Clock,
  Rows,
} from "lucide-react";
import { api, SqlResponse } from "@/lib/api";

interface SqlStudioViewProps {
  onTelemetryUpdate: (traceId: string, latencyMs: number) => void;
}

const PRESET_SQL_QUERIES = [
  "Show total travel expenses grouped by department",
  "Show top 5 highest expenses with employee names and amounts",
  "List total operational expenses by category for current quarter",
  "Count total number of employees per department",
];

export default function SqlStudioView({ onTelemetryUpdate }: SqlStudioViewProps) {
  const [naturalQuery, setNaturalQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SqlResponse | null>(null);
  const [copiedSql, setCopiedSql] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleExecute = async (queryToRun?: string) => {
    const q = (queryToRun || naturalQuery).trim();
    if (!q || loading) return;

    setLoading(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const response = await api.querySql(q);
      setResult(response);
      onTelemetryUpdate(`sql_trace_${Date.now()}`, response.execution_time_ms);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to execute SQL query";
      setErrorMsg(message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopySql = () => {
    if (!result?.synthesized_sql) return;
    navigator.clipboard.writeText(result.synthesized_sql);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  return (
    <div className="fade-in">
      {/* Studio Header Card */}
      <div className="omnibox-wrapper">
        <div className="omnibox-card">
          <div className="omnibox-header">
            <div className="omnibox-title">
              <Database size={18} color="var(--brand-amber)" />
              Secure 5-Gate Natural-Language Text-to-SQL Studio
            </div>
            <span className="route-pill route-pill-sql">
              <ShieldCheck size={12} />
              Read-Only Sandboxed Pool
            </span>
          </div>

          <div className="search-input-group">
            <textarea
              className="omnibox-textarea"
              placeholder="Ask for any financial, expense, or departmental data in plain English..."
              value={naturalQuery}
              onChange={(e) => setNaturalQuery(e.target.value)}
              disabled={loading}
              rows={2}
            />
            <button
              className="btn-primary"
              style={{
                background: "linear-gradient(135deg, #d97706 0%, #b45309 100%)",
                boxShadow: "0 4px 14px rgba(217, 119, 6, 0.35)",
              }}
              onClick={() => handleExecute()}
              disabled={loading || !naturalQuery.trim()}
            >
              {loading ? <Cpu size={16} className="animate-spin" /> : <Play size={16} />}
              {loading ? "Synthesizing..." : "Execute Query"}
            </button>
          </div>

          {/* Quick Presets */}
          <div className="quick-chips-wrapper">
            <span className="chip-label">Quick Analytics Queries:</span>
            {PRESET_SQL_QUERIES.map((query, i) => (
              <button
                key={i}
                className="quick-chip"
                onClick={() => {
                  setNaturalQuery(query);
                  handleExecute(query);
                }}
              >
                {query}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 5-Gate Defense Visualizer */}
      <div className="gates-checklist">
        <div className="gate-badge">
          <ShieldCheck size={14} color="var(--brand-emerald)" />
          Gate 1: Schema Resolution
        </div>
        <div className="gate-badge">
          <ShieldCheck size={14} color="var(--brand-emerald)" />
          Gate 2: sqlglot AST Check (SELECT only)
        </div>
        <div className="gate-badge">
          <ShieldCheck size={14} color="var(--brand-emerald)" />
          Gate 3: Table Whitelisting
        </div>
        <div className="gate-badge">
          <ShieldCheck size={14} color="var(--brand-emerald)" />
          Gate 4: Tenant Boundary & LIMIT 100
        </div>
        <div className="gate-badge">
          <ShieldCheck size={14} color="var(--brand-emerald)" />
          Gate 5: 3s Hard Statement Timeout
        </div>
      </div>

      {errorMsg && (
        <div
          className="glass-panel"
          style={{
            padding: "16px 20px",
            borderColor: "rgba(244, 63, 94, 0.4)",
            background: "rgba(244, 63, 94, 0.1)",
            color: "#fecdd3",
            marginBottom: "24px",
          }}
        >
          <strong>Security or Execution Error:</strong> {errorMsg}
        </div>
      )}

      {/* Result Display */}
      {result && (
        <div className="glass-panel" style={{ padding: "24px", marginBottom: "70px" }}>
          {/* Metadata bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "16px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.82rem" }}>
                <Clock size={14} color="var(--text-muted)" />
                <span>Execution Time:</span>
                <strong style={{ color: "var(--brand-amber)" }}>
                  {result.execution_time_ms} ms
                </strong>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.82rem" }}>
                <Rows size={14} color="var(--text-muted)" />
                <span>Rows Returned:</span>
                <strong style={{ color: "var(--brand-emerald)" }}>{result.row_count}</strong>
              </div>
            </div>

            <button
              className="nav-tab-btn"
              onClick={handleCopySql}
              style={{ padding: "6px 12px", fontSize: "0.76rem" }}
            >
              {copiedSql ? <Check size={13} color="var(--brand-emerald)" /> : <Copy size={13} />}
              {copiedSql ? "Copied SQL" : "Copy SQL"}
            </button>
          </div>

          {/* Generated SQL Code Block */}
          <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--brand-amber)", marginBottom: "6px" }}>
            SYNTHESIZED & AUDITED SQL STATEMENT
          </div>
          <pre className="sql-code-block">{result.synthesized_sql}</pre>

          {/* Tabular Data View */}
          <div style={{ marginTop: "20px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "0.84rem",
                fontWeight: 600,
                color: "var(--text-accent)",
                marginBottom: "10px",
              }}
            >
              <Table size={16} /> Result Grid ({result.row_count} records)
            </div>

            {result.data.length > 0 ? (
              <div className="data-table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      {result.columns.map((col, idx) => (
                        <th key={idx}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.data.map((row, rIdx) => (
                      <tr key={rIdx}>
                        {result.columns.map((col, cIdx) => (
                          <td key={cIdx}>{String(row[col] ?? "—")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div
                style={{
                  padding: "24px",
                  textAlign: "center",
                  color: "var(--text-muted)",
                  background: "rgba(15, 23, 42, 0.4)",
                  borderRadius: "8px",
                }}
              >
                Query executed successfully, but 0 rows matched the tenant criteria.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
