"use client";

import React, { useState } from "react";
import {
  Send,
  Sparkles,
  FileText,
  Database,
  Layers,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  ExternalLink,
  Cpu,
} from "lucide-react";
import { api, AgentResponse } from "@/lib/api";

interface UnifiedChatViewProps {
  onTelemetryUpdate: (traceId: string, latencyMs: number) => void;
}

const SAMPLE_QUERIES = [
  {
    text: "What is our company travel meal daily allowance?",
    route: "RAG",
    tag: "Policy RAG",
  },
  {
    text: "Show total expenses grouped by department",
    route: "SQL",
    tag: "Text-to-SQL",
  },
  {
    text: "Compare our travel policy daily allowance limits with actual Engineering expenses to find non-compliant claims.",
    route: "HYBRID_AGENT",
    tag: "Hybrid Agent",
  },
];

function FormattedAnswer({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let currentList: React.ReactNode[] = [];
  let inList = false;

  const flushList = () => {
    if (inList && currentList.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="markdown-list">
          {currentList}
        </ul>
      );
      currentList = [];
      inList = false;
    }
  };

  const formatInline = (str: string): React.ReactNode => {
    const parts = str.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={i} style={{ color: "#fff", fontWeight: 600 }}>
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code
            key={i}
            style={{
              padding: "2px 6px",
              borderRadius: "4px",
              background: "rgba(99, 102, 241, 0.15)",
              color: "var(--brand-cyan)",
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: "0.82em",
              wordBreak: "break-all",
            }}
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      return;
    }

    if (trimmed.startsWith("### ")) {
      flushList();
      elements.push(
        <h4 key={idx} className="markdown-h4">
          {formatInline(trimmed.slice(4))}
        </h4>
      );
    } else if (trimmed.startsWith("## ")) {
      flushList();
      elements.push(
        <h3 key={idx} className="markdown-h3">
          {formatInline(trimmed.slice(3))}
        </h3>
      );
    } else if (trimmed.startsWith("# ")) {
      flushList();
      elements.push(
        <h2 key={idx} className="markdown-h2">
          {formatInline(trimmed.slice(2))}
        </h2>
      );
    } else if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
      inList = true;
      const isIndented = line.startsWith("  ") || line.startsWith("    ");
      currentList.push(
        <li
          key={idx}
          className={`markdown-li ${isIndented ? "markdown-li-nested" : ""}`}
        >
          {formatInline(trimmed.slice(2))}
        </li>
      );
    } else {
      flushList();
      if (trimmed.startsWith("**") && trimmed.endsWith("**") && trimmed.length < 60) {
        elements.push(
          <div key={idx} className="markdown-highlight-header">
            {formatInline(trimmed)}
          </div>
        );
      } else {
        elements.push(
          <p key={idx} className="markdown-p">
            {formatInline(trimmed)}
          </p>
        );
      }
    }
  });

  flushList();

  return <div className="formatted-answer-container">{elements}</div>;
}

export default function UnifiedChatView({ onTelemetryUpdate }: UnifiedChatViewProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [showSteps, setShowSteps] = useState(false);

  const handleSend = async (queryText?: string) => {
    const textToRun = (queryText || query).trim();
    if (!textToRun || loading) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await api.queryAgent(textToRun);
      setResult(response);
      onTelemetryUpdate(response.trace_id, response.execution_time_ms);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to execute query";
      setResult({
        prompt: textToRun,
        query: textToRun,
        detected_route: "RAG",
        routing_reason: "Error encountered",
        final_answer: `Error: ${message}. Make sure your local FastAPI backend is running at http://localhost:8000.`,
        execution_time_ms: 0,
        trace_id: "err_fallback",
        reasoning_steps: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.final_answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fade-in">
      {/* Omnibox Search Card */}
      <div className="omnibox-wrapper">
        <div className="omnibox-card">
          <div className="omnibox-header">
            <div className="omnibox-title">
              <Sparkles size={18} color="var(--brand-indigo)" />
              Enterprise Intelligence Console
            </div>
            {result && (
              <span
                className={`route-pill ${
                  result.detected_route === "RAG"
                    ? "route-pill-rag"
                    : result.detected_route === "SQL"
                    ? "route-pill-sql"
                    : "route-pill-agent"
                }`}
              >
                {result.detected_route === "RAG" && <FileText size={12} />}
                {result.detected_route === "SQL" && <Database size={12} />}
                {result.detected_route === "HYBRID_AGENT" && <Layers size={12} />}
                Routed To: {result.detected_route}
              </span>
            )}
          </div>

          <div className="search-input-group">
            <textarea
              className="omnibox-textarea"
              placeholder="Ask any policy question, query operational financial metrics, or request an audited cross-system compliance comparison..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              rows={2}
            />
            <button
              className="btn-primary"
              onClick={() => handleSend()}
              disabled={loading || !query.trim()}
            >
              {loading ? (
                <Cpu size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
              {loading ? "Analyzing..." : "Ask Intelligence"}
            </button>
          </div>

          {/* Quick Suggestion Chips */}
          <div className="quick-chips-wrapper">
            <span className="chip-label">Sample Enterprise Inquiries:</span>
            {SAMPLE_QUERIES.map((item, idx) => (
              <button
                key={idx}
                className="quick-chip"
                onClick={() => {
                  setQuery(item.text);
                  handleSend(item.text);
                }}
              >
                <span style={{ color: "var(--brand-indigo)", marginRight: "4px" }}>
                  [{item.tag}]
                </span>
                {item.text}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Answer & Result Presentation */}
      <div className="intelligence-grid">
        {loading && (
          <div className="glass-panel" style={{ padding: "40px", textAlign: "center" }}>
            <div
              style={{
                display: "inline-block",
                marginBottom: "16px",
                color: "var(--brand-indigo)",
              }}
            >
              <Cpu size={36} />
            </div>
            <h3 style={{ fontSize: "1.1rem", marginBottom: "8px" }}>
              Classifying Intent & Executing Multi-Hop Routing...
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.86rem" }}>
              Evaluating AST constraints, querying vector indices, and validating compliance rules.
            </p>
          </div>
        )}

        {result && (
          <div className="glass-panel answer-card">
            {/* Header */}
            <div className="answer-header">
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "8px",
                    background: "rgba(99, 102, 241, 0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--brand-indigo)",
                  }}
                >
                  <Sparkles size={16} />
                </div>
                <div>
                  <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Grounded Intelligence Response</h3>
                  <div style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                    Executed in {result.execution_time_ms} ms via {result.detected_route}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button
                  className="nav-tab-btn"
                  onClick={handleCopy}
                  style={{ padding: "6px 12px", fontSize: "0.78rem" }}
                  title="Copy answer"
                >
                  {copied ? <Check size={14} color="var(--brand-emerald)" /> : <Copy size={14} />}
                  {copied ? "Copied" : "Copy"}
                </button>
                <button
                  className="nav-tab-btn"
                  onClick={() => setShowSteps(!showSteps)}
                  style={{ padding: "6px 12px", fontSize: "0.78rem" }}
                  title="Toggle multi-hop reasoning steps"
                >
                  {showSteps ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  {showSteps ? "Hide Reasoning" : "View Reasoning"}
                </button>
              </div>
            </div>

            {/* Stepper / Timeline */}
            {showSteps && result.reasoning_steps.length > 0 && (
              <div style={{ marginBottom: "20px" }}>
                <div className="stepper-timeline">
                  {result.reasoning_steps.map((st) => (
                    <div key={st.step} className="stepper-node active">
                      <div className="node-icon-box">{st.step}</div>
                      <div>
                        <div className="node-info-title">{st.node}: {st.action}</div>
                        {st.details && (
                          <div className="node-info-detail">{st.details}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Main Answer Text */}
            <div className="answer-body">
              <FormattedAnswer text={result.final_answer} />
            </div>

            {/* SQL Context View if present */}
            {result.sql_context?.sql && (
              <div style={{ marginTop: "20px" }}>
                <div className="citations-title">
                  <Database size={14} /> Synthesized SQL (5-Gate Guarded)
                </div>
                <pre className="sql-code-block">{result.sql_context.sql}</pre>
              </div>
            )}

            {/* Document Citations if present */}
            {result.rag_context?.citations && result.rag_context.citations.length > 0 && (
              <div className="citations-wrapper">
                <div className="citations-title">
                  <FileText size={14} /> Source Document Citations ({result.rag_context.citations.length})
                </div>
                <div className="citation-cards-grid">
                  {result.rag_context.citations.map((c, i) => (
                    <div key={i} className="citation-card">
                      <div className="citation-doc-title">{c.document_title || "Policy Document"}</div>
                      <div className="citation-chunk-id">Chunk ID: {(c.chunk_id || "").slice(0, 18)}...</div>
                      {c.relevance_score && (
                        <div style={{ fontSize: "0.72rem", color: "var(--brand-emerald)", marginTop: "4px" }}>
                          RRF Score: {(c.relevance_score * 100).toFixed(1)}% match
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
    </div>
  );
}
