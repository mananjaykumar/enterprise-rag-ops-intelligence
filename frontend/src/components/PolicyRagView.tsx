"use client";

import React, { useState } from "react";
import {
  FileText,
  Search,
  CheckCircle,
  Copy,
  Check,
  Cpu,
  Layers,
  Sparkles,
  Sliders,
  ShieldCheck,
} from "lucide-react";
import { api, RagResponse } from "@/lib/api";

interface PolicyRagViewProps {
  onTelemetryUpdate: (traceId: string, latencyMs: number) => void;
}

const POLICY_PRESETS = [
  "What is our company travel meal daily allowance?",
  "What are the requirements for home office hardware reimbursement?",
  "What is the policy regarding confidential source code on personal devices?",
  "How many days in advance must international business travel be submitted?",
];

export default function PolicyRagView({ onTelemetryUpdate }: PolicyRagViewProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(3);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RagResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSearch = async (qToRun?: string) => {
    const q = (qToRun || query).trim();
    if (!q || loading) return;

    setLoading(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const response = await api.queryRag(q, topK);
      setResult(response);
      onTelemetryUpdate(`rag_trace_${Date.now()}`, response.execution_time_ms);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to retrieve policy documents";
      setErrorMsg(message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result?.answer) return;
    navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fade-in">
      {/* Search Header */}
      <div className="omnibox-wrapper">
        <div className="omnibox-card">
          <div className="omnibox-header">
            <div className="omnibox-title">
              <FileText size={18} color="var(--brand-cyan)" />
              Two-Tier Grounded Policy RAG Explorer
            </div>
            <span className="route-pill route-pill-rag">
              <ShieldCheck size={12} />
              Pre-Retrieval RBAC Filtered
            </span>
          </div>

          <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", marginBottom: "16px" }}>
            Combines PostgreSQL Full-Text Search with dense 768-d pgvector cosine distance, fused via
            Reciprocal Rank Fusion (RRF) and scored with the lightweight FlashRank ONNX cross-encoder.
          </p>

          <div className="search-input-group">
            <textarea
              className="omnibox-textarea"
              placeholder="Search company policies, security guidelines, or corporate handbooks..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
              rows={2}
            />
            <button
              className="btn-primary"
              style={{
                background: "linear-gradient(135deg, var(--brand-cyan) 0%, #0e7490 100%)",
                boxShadow: "0 4px 14px rgba(6, 182, 212, 0.35)",
              }}
              onClick={() => handleSearch()}
              disabled={loading || !query.trim()}
            >
              {loading ? <Cpu size={16} className="animate-spin" /> : <Search size={16} />}
              {loading ? "Reranking..." : "Search Policy"}
            </button>
          </div>

          {/* Top-K Slider & Presets */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              marginTop: "14px",
            }}
          >
            <div className="quick-chips-wrapper" style={{ margin: 0 }}>
              <span className="chip-label">Policy Presets:</span>
              {POLICY_PRESETS.map((p, i) => (
                <button
                  key={i}
                  className="quick-chip"
                  onClick={() => {
                    setQuery(p);
                    handleSearch(p);
                  }}
                >
                  {p}
                </button>
              ))}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
              <Sliders size={14} color="var(--brand-cyan)" />
              <span>Context Candidates (Top-K):</span>
              <select
                className="persona-select"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                style={{ padding: "4px 8px" }}
              >
                <option value={1}>Top 1</option>
                <option value={2}>Top 2</option>
                <option value={3}>Top 3 (Default)</option>
                <option value={5}>Top 5</option>
              </select>
            </div>
          </div>
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
          <strong>Retrieval Notice:</strong> {errorMsg}
        </div>
      )}

      {/* RAG Answer Display */}
      {result && (
        <div className="glass-panel answer-card" style={{ marginBottom: "70px" }}>
          <div className="answer-header">
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "rgba(6, 182, 212, 0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--brand-cyan)",
                }}
              >
                <Sparkles size={16} />
              </div>
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Grounded Policy Answer</h3>
                <div style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                  FlashRank Reranked & Gemini Synthesized in {result.execution_time_ms} ms
                </div>
              </div>
            </div>

            <button
              className="nav-tab-btn"
              onClick={handleCopy}
              style={{ padding: "6px 12px", fontSize: "0.78rem" }}
            >
              {copied ? <Check size={14} color="var(--brand-emerald)" /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>

          <div className="answer-body">
            <p style={{ whiteSpace: "pre-line" }}>{result.answer}</p>
          </div>

          {/* Citations List */}
          {result.citations.length > 0 && (
            <div className="citations-wrapper">
              <div className="citations-title">
                <FileText size={14} /> Grounded Citation Lineage ({result.citations.length} sources)
              </div>
              <div className="citation-cards-grid">
                {result.citations.map((c, idx) => (
                  <div key={idx} className="citation-card">
                    <div className="citation-doc-title">{c.document_title}</div>
                    <div className="citation-chunk-id">Chunk ID: {(c.chunk_id || "").slice(0, 18)}...</div>
                    {c.relevance_score && (
                      <div style={{ fontSize: "0.72rem", color: "var(--brand-emerald)", marginTop: "4px" }}>
                        Confidence Match: {(c.relevance_score * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
