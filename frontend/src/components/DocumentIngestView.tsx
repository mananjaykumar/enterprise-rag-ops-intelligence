"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  Layers,
  ShieldCheck,
  FileCheck,
  Cpu,
  Lock,
  Search,
  AlertCircle,
  X,
  RefreshCw,
  Clock,
  History,
  Archive,
  Copy,
  Check,
  Code,
  FileJson,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";

interface DocumentIngestViewProps {
  isAuthenticated: boolean;
  onOpenAuth: () => void;
  currentUserRole?: string;
  currentUserTenant?: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  filename: string;
  type: string;
  chunks: number;
  status: "ACTIVE" | "SUPERSEDED" | "PROCESSING" | "PENDING" | "FAILED" | "ARCHIVED";
  isActive: boolean;
  date: string;
  tenant: string;
  allowedRoles: string[];
}

export default function DocumentIngestView({
  isAuthenticated,
  onOpenAuth,
  currentUserRole,
  currentUserTenant,
}: DocumentIngestViewProps) {
  const [dragActive, setDragActive] = useState(false);
  const dragCounter = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docTitle, setDocTitle] = useState("");
  const [allowedRolesStr, setAllowedRolesStr] = useState("admin,manager,analyst");
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Live Knowledge Base verification search
  const [verifyQuery, setVerifyQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchViewMode, setSearchViewMode] = useState<"cards" | "json">("cards");
  const [copiedChunkIdx, setCopiedChunkIdx] = useState<number | null>(null);
  const [copiedJson, setCopiedJson] = useState(false);
  const [expandedChunks, setExpandedChunks] = useState<Record<number, boolean>>({});

  // Fetch documents live from the backend
  const fetchDocuments = useCallback(async () => {
    if (!isAuthenticated) {
      setDocuments([]);
      return;
    }
    setLoadingDocs(true);
    try {
      const docs = await api.listDocuments();
      if (Array.isArray(docs) && docs.length > 0) {
        const items: DocumentItem[] = docs.map((d: any) => {
          // Derive display type from mime_type or filename extension
          const ext = d.filename?.split(".").pop()?.toUpperCase() || "FILE";
          const mimeMap: Record<string, string> = {
            "application/pdf": "PDF",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
            "text/plain": "TXT",
            "text/markdown": "MD",
          };
          const displayType = mimeMap[d.mime_type] || ext;

          // Directly sync with backend DocumentLifecycleStatus enum
          const rawStatus = (d.status || "PENDING").toUpperCase();
          const mappedStatus: DocumentItem["status"] =
            rawStatus === "ACTIVE" ? "ACTIVE"
            : rawStatus === "SUPERSEDED" ? "SUPERSEDED"
            : rawStatus === "PROCESSING" ? "PROCESSING"
            : rawStatus === "FAILED" ? "FAILED"
            : rawStatus === "ARCHIVED" ? "ARCHIVED"
            : "PENDING";

          return {
            id: String(d.id),
            title: d.title || d.filename,
            filename: d.filename,
            type: displayType,
            chunks: d.chunk_count ?? 0,
            status: mappedStatus,
            isActive: Boolean(d.is_active),
            date: d.created_at ? d.created_at.split("T")[0] : new Date().toISOString().split("T")[0],
            tenant: currentUserTenant || "default_tenant",
            allowedRoles: d.allowed_roles || ["admin", "manager", "analyst"],
          };
        });
        setDocuments(items);
      } else {
        setDocuments([]);
      }
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  }, [isAuthenticated, currentUserTenant]);

  // Load documents when auth state changes
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Auto-sync document lineage status with backend while any document is in PENDING or PROCESSING state
  useEffect(() => {
    const hasPendingOrProcessing = documents.some(
      (doc) => doc.status === "PENDING" || doc.status === "PROCESSING"
    );
    if (!hasPendingOrProcessing || !isAuthenticated) return;

    const syncInterval = setInterval(() => {
      fetchDocuments();
    }, 3000);

    return () => clearInterval(syncInterval);
  }, [documents, isAuthenticated, fetchDocuments]);

  // 1. DRAG AND DROP HANDLERS
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setDragActive(true);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    if (!dragActive) setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      setDragActive(false);
      dragCounter.current = 0;
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    dragCounter.current = 0;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processSelectedFile(e.target.files[0]);
    }
  };

  const processSelectedFile = (file: File) => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    const validExts = [".pdf", ".docx", ".doc", ".md", ".txt"];
    if (!validExts.includes(ext)) {
      setUploadError(`Unsupported format '${ext}'. Allowed: .pdf, .docx, .md, .txt`);
      return;
    }
    setUploadError(null);
    setSelectedFile(file);
    const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
    setDocTitle(nameWithoutExt.charAt(0).toUpperCase() + nameWithoutExt.slice(1));
  };

  const handleClearSelection = () => {
    setSelectedFile(null);
    setDocTitle("");
    setUploadError(null);
    setUploadSuccess(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // 2. DOCUMENT UPLOAD & INGESTION
  const handleUpload = async () => {
    if (!selectedFile || !docTitle.trim()) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      await api.uploadDocument(selectedFile, docTitle.trim());
      setUploadSuccess(`'${docTitle.trim()}' uploaded and queued for vector indexing.`);
      setSelectedFile(null);
      setDocTitle("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      // Refresh the list from backend
      await fetchDocuments();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  // 3. LIVE KNOWLEDGE BASE SEARCH VERIFICATION
  const handleVerifySearch = async () => {
    if (!verifyQuery.trim()) return;
    setSearching(true);
    try {
      const results = await api.searchKnowledgeBase(verifyQuery.trim());
      setSearchResults(results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="fade-in">
      {/* Not Authenticated */}
      {!isAuthenticated ? (
        <div
          className="glass-panel"
          style={{
            padding: "48px 24px",
            textAlign: "center",
            marginTop: "24px",
            marginBottom: "70px",
            borderRadius: "16px",
            border: "1px solid rgba(244, 63, 94, 0.3)",
            background: "linear-gradient(180deg, rgba(244, 63, 94, 0.05) 0%, rgba(15, 23, 42, 0.8) 100%)",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              background: "rgba(244, 63, 94, 0.15)",
              color: "var(--brand-rose)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
            }}
          >
            <Lock size={26} />
          </div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: "8px" }}>
            Authorized Access Required
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.92rem", maxWidth: "560px", margin: "0 auto 20px" }}>
            The enterprise knowledge base and document ingestion pipeline are strictly isolated under
            tenant-boundary RBAC. Please sign in to view and upload policy documents.
          </p>
          <button
            className="btn-primary"
            onClick={onOpenAuth}
            style={{ margin: "0 auto", padding: "10px 24px" }}
          >
            Sign In to Access Knowledge Base
          </button>
        </div>
      ) : (
        <>
          {/* Document Ingestion Card */}
          <div className="omnibox-wrapper">
            <div className="omnibox-card">
              <div className="omnibox-header">
                <div className="omnibox-title">
                  <UploadCloud size={18} color="var(--brand-cyan)" />
                  Enterprise Document Ingestion & Chunk Lineage
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className="route-pill route-pill-rag">
                    <ShieldCheck size={12} />
                    Tenant: {currentUserTenant || "default_tenant"}
                  </span>
                  <span
                    className="route-pill"
                    style={{ background: "rgba(16, 185, 129, 0.15)", color: "var(--brand-emerald)" }}
                  >
                    Role: {currentUserRole?.toUpperCase() || "ADMIN"}
                  </span>
                </div>
              </div>

              <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", marginBottom: "16px" }}>
                Upload corporate policy manuals, standard operating procedures, or compliance guidelines.
                The ingestion worker parses structural content, extracts schemas, and indexes 768-d Gemini vectors.
              </p>

              {/* Drag & Drop Zone */}
              <div
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${dragActive ? "var(--brand-cyan)" : "var(--border-subtle)"}`,
                  borderRadius: "12px",
                  padding: selectedFile ? "24px 20px" : "36px 20px",
                  textAlign: "center",
                  background: dragActive
                    ? "rgba(6, 182, 212, 0.12)"
                    : selectedFile
                    ? "rgba(99, 102, 241, 0.08)"
                    : "rgba(15, 23, 42, 0.6)",
                  boxShadow: dragActive ? "0 0 24px rgba(6, 182, 212, 0.25)" : "none",
                  transition: "all 0.2s ease",
                  cursor: "pointer",
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.md,.txt"
                  style={{ display: "none" }}
                  onChange={handleFileInputChange}
                />
                <div style={{ pointerEvents: "none" }}>
                  <div
                    style={{
                      color: selectedFile ? "var(--brand-indigo)" : "var(--brand-cyan)",
                      marginBottom: "10px",
                    }}
                  >
                    <UploadCloud size={36} style={{ margin: "0 auto" }} />
                  </div>
                  {selectedFile ? (
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "1rem", color: "#fff", marginBottom: "4px" }}>
                        {selectedFile.name}
                      </div>
                      <div style={{ fontSize: "0.8rem", color: "var(--brand-emerald)" }}>
                        {(selectedFile.size / 1024).toFixed(1)} KB · Ready to Ingest
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: "0.96rem",
                          marginBottom: "4px",
                          color: dragActive ? "var(--brand-cyan)" : "#fff",
                        }}
                      >
                        {dragActive ? "Drop document here!" : "Drag & drop file here, or click to browse"}
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                        Supported: PDF, Word (.docx), Markdown (.md), Plain Text (.txt)
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* File Config Panel */}
              {selectedFile && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "16px",
                    background: "rgba(15, 23, 42, 0.8)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "10px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--brand-indigo)" }}>
                      Document Metadata Configuration
                    </span>
                    <button
                      onClick={handleClearSelection}
                      className="nav-tab-btn"
                      style={{ padding: "4px 8px", fontSize: "0.74rem" }}
                    >
                      <X size={13} /> Clear
                    </button>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "12px" }}>
                    <div>
                      <label
                        style={{
                          fontSize: "0.76rem",
                          color: "var(--text-muted)",
                          display: "block",
                          marginBottom: "4px",
                        }}
                      >
                        Document Title
                      </label>
                      <input
                        type="text"
                        className="omnibox-textarea"
                        style={{ minHeight: "40px", maxHeight: "40px", padding: "8px 12px", fontSize: "0.86rem" }}
                        placeholder="Formal Document Title..."
                        value={docTitle}
                        onChange={(e) => setDocTitle(e.target.value)}
                      />
                    </div>
                    <div>
                      <label
                        style={{
                          fontSize: "0.76rem",
                          color: "var(--text-muted)",
                          display: "block",
                          marginBottom: "4px",
                        }}
                      >
                        Allowed Roles (RBAC)
                      </label>
                      <input
                        type="text"
                        className="omnibox-textarea"
                        style={{ minHeight: "40px", maxHeight: "40px", padding: "8px 12px", fontSize: "0.86rem" }}
                        value={allowedRolesStr}
                        onChange={(e) => setAllowedRolesStr(e.target.value)}
                        placeholder="admin,manager,analyst"
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <button
                      className="btn-primary"
                      onClick={handleUpload}
                      disabled={uploading || !docTitle.trim()}
                      style={{ padding: "10px 20px" }}
                    >
                      {uploading ? <Cpu size={16} className="animate-spin" /> : <UploadCloud size={16} />}
                      {uploading ? "Parsing & Indexing..." : "Ingest Document"}
                    </button>
                  </div>
                </div>
              )}

              {/* Success Banner */}
              {uploadSuccess && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px 16px",
                    background: "rgba(16, 185, 129, 0.12)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    borderRadius: "8px",
                    color: "var(--brand-emerald)",
                    fontSize: "0.84rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>{uploadSuccess}</span>
                </div>
              )}

              {/* Error Banner */}
              {uploadError && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px 16px",
                    background: "rgba(244, 63, 94, 0.12)",
                    border: "1px solid rgba(244, 63, 94, 0.3)",
                    borderRadius: "8px",
                    color: "var(--brand-rose)",
                    fontSize: "0.84rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <AlertCircle size={16} />
                  <span>{uploadError}</span>
                </div>
              )}
            </div>
          </div>

          {/* Active Knowledge Base Catalog */}
          <div className="glass-panel" style={{ padding: "24px", marginBottom: "30px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "12px",
                marginBottom: "16px",
              }}
            >
              <h3
                style={{
                  fontSize: "1rem",
                  fontWeight: 600,
                  margin: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <FileCheck size={18} color="var(--brand-cyan)" />
                Active Knowledge Base Catalog ({documents.length} Document{documents.length !== 1 ? "s" : ""})
              </h3>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {documents.some((d) => d.status === "PENDING" || d.status === "PROCESSING") && (
                  <span
                    style={{
                      fontSize: "0.74rem",
                      color: "var(--brand-cyan)",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      padding: "3px 8px",
                      borderRadius: "4px",
                      background: "rgba(6, 182, 212, 0.1)",
                      border: "1px solid rgba(6, 182, 212, 0.25)",
                    }}
                  >
                    <RefreshCw size={11} className="animate-spin" />
                    Auto-syncing with worker
                  </span>
                )}
                <span
                  style={{
                    fontSize: "0.76rem",
                    padding: "4px 10px",
                    borderRadius: "4px",
                    background: "rgba(99, 102, 241, 0.12)",
                    border: "1px solid rgba(99, 102, 241, 0.25)",
                    color: "var(--brand-indigo)",
                  }}
                >
                  Tenant: {currentUserTenant || "default_tenant"}
                </span>
                <button
                  onClick={fetchDocuments}
                  className="nav-tab-btn"
                  style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                  title="Refresh document list"
                  disabled={loadingDocs}
                >
                  <RefreshCw size={13} className={loadingDocs ? "animate-spin" : ""} />
                  Refresh
                </button>
              </div>
            </div>

            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Document Title</th>
                    <th>File Format</th>
                    <th>Vector Chunks</th>
                    <th>Lineage Status</th>
                    <th>Tenant Context</th>
                    <th>Indexed Date</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingDocs ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", padding: "40px 16px", color: "var(--text-muted)" }}>
                        <Cpu size={24} style={{ margin: "0 auto 10px", display: "block", opacity: 0.4 }} />
                        <div style={{ fontSize: "0.84rem" }}>Loading documents...</div>
                      </td>
                    </tr>
                  ) : documents.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        style={{ textAlign: "center", padding: "48px 16px", color: "var(--text-muted)" }}
                      >
                        <FileText
                          size={36}
                          style={{ margin: "0 auto 14px", opacity: 0.25, display: "block" }}
                        />
                        <div
                          style={{
                            fontWeight: 600,
                            color: "var(--text-secondary)",
                            marginBottom: "6px",
                            fontSize: "0.95rem",
                          }}
                        >
                          No documents ingested yet
                        </div>
                        <div style={{ fontSize: "0.8rem" }}>
                          Drag and drop a PDF or other document above to parse, chunk, and index it into the
                          vector database.
                        </div>
                      </td>
                    </tr>
                  ) : (
                    documents.map((doc) => (
                      <tr key={doc.id}>
                        <td>
                          <div style={{ fontWeight: 600, color: "#fff" }}>{doc.title}</div>
                          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{doc.filename}</div>
                        </td>
                        <td>
                          <span
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: 700,
                              padding: "2px 6px",
                              borderRadius: "4px",
                              background: "rgba(255,255,255,0.08)",
                              color: "var(--brand-cyan)",
                            }}
                          >
                            {doc.type}
                          </span>
                        </td>
                        <td>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "5px",
                              color: "var(--brand-indigo)",
                              fontWeight: 600,
                            }}
                          >
                            <Layers size={13} />
                            {doc.chunks}
                          </div>
                        </td>
                        <td>
                          {doc.status === "ACTIVE" ? (
                            <span
                              className="telemetry-badge telemetry-badge-emerald"
                              style={{ fontWeight: 600 }}
                              title="Active in live retrieval vector index"
                            >
                              <CheckCircle2 size={12} />
                              ACTIVE
                            </span>
                          ) : doc.status === "SUPERSEDED" ? (
                            <span
                              className="telemetry-badge telemetry-badge-amber"
                              style={{ fontWeight: 600 }}
                              title="Historical version superseded in lineage by a newer document"
                            >
                              <History size={12} />
                              SUPERSEDED
                            </span>
                          ) : doc.status === "PROCESSING" ? (
                            <span
                              className="telemetry-badge telemetry-badge-indigo"
                              style={{ fontWeight: 600 }}
                              title="Currently parsing markdown AST and generating embeddings"
                            >
                              <RefreshCw size={12} className="animate-spin" />
                              PROCESSING
                            </span>
                          ) : doc.status === "FAILED" ? (
                            <span
                              className="telemetry-badge telemetry-badge-rose"
                              style={{ fontWeight: 600 }}
                              title="Ingestion failed"
                            >
                              <AlertCircle size={12} />
                              FAILED
                            </span>
                          ) : doc.status === "ARCHIVED" ? (
                            <span
                              className="telemetry-badge"
                              style={{ fontWeight: 600, color: "var(--text-muted)" }}
                              title="Archived document"
                            >
                              <Archive size={12} />
                              ARCHIVED
                            </span>
                          ) : (
                            <span
                              className="telemetry-badge telemetry-badge-cyan"
                              style={{ fontWeight: 600 }}
                              title="Queued in background pipeline"
                            >
                              <Clock size={12} />
                              PENDING
                            </span>
                          )}
                        </td>
                        <td>
                          <span
                            style={{
                              fontSize: "0.76rem",
                              color: "var(--text-secondary)",
                              fontFamily: "monospace",
                            }}
                          >
                            {doc.tenant}
                          </span>
                        </td>
                        <td style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{doc.date}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Live Knowledge Base Search Verification */}
          <div className="glass-panel" style={{ padding: "24px", marginBottom: "70px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
              <div>
                <h3
                  style={{
                    fontSize: "0.96rem",
                    fontWeight: 600,
                    margin: 0,
                    marginBottom: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <Search size={16} color="var(--brand-emerald)" />
                  Live Knowledge Base Verification (Hybrid RAG Search)
                </h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.84rem", margin: 0 }}>
                  Test vector and full-text chunk retrieval on your authenticated tenant documents in real-time.
                </p>
              </div>

              {searchResults && searchResults.length > 0 && (
                <div style={{ display: "flex", gap: "6px", background: "rgba(15, 23, 42, 0.8)", padding: "4px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                  <button
                    onClick={() => setSearchViewMode("cards")}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "6px",
                      fontSize: "0.76rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "5px",
                      background: searchViewMode === "cards" ? "rgba(99, 102, 241, 0.25)" : "transparent",
                      color: searchViewMode === "cards" ? "#fff" : "var(--text-muted)",
                      border: searchViewMode === "cards" ? "1px solid rgba(99, 102, 241, 0.4)" : "1px solid transparent",
                    }}
                  >
                    <Layers size={13} />
                    Full Cards ({searchResults.length})
                  </button>
                  <button
                    onClick={() => setSearchViewMode("json")}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "6px",
                      fontSize: "0.76rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "5px",
                      background: searchViewMode === "json" ? "rgba(99, 102, 241, 0.25)" : "transparent",
                      color: searchViewMode === "json" ? "#fff" : "var(--text-muted)",
                      border: searchViewMode === "json" ? "1px solid rgba(99, 102, 241, 0.4)" : "1px solid transparent",
                    }}
                  >
                    <FileJson size={13} />
                    Raw JSON Payload
                  </button>
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <input
                type="text"
                className="omnibox-textarea"
                style={{ minHeight: "42px", maxHeight: "42px", padding: "10px 14px", fontSize: "0.88rem" }}
                placeholder="Search indexed policies (e.g. 'meal allowance', 'travel limit')..."
                value={verifyQuery}
                onChange={(e) => setVerifyQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleVerifySearch();
                }}
              />
              <button
                className="btn-primary"
                onClick={handleVerifySearch}
                disabled={searching || !verifyQuery.trim()}
                style={{
                  background: "linear-gradient(135deg, var(--brand-emerald) 0%, #059669 100%)",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.3)",
                }}
              >
                {searching ? <Cpu size={15} className="animate-spin" /> : <Search size={15} />}
                {searching ? "Searching..." : "Search Chunks"}
              </button>
            </div>

            {searchResults && (
              <div style={{ marginTop: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                  <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                    Found <strong style={{ color: "#fff" }}>{searchResults.length}</strong> matching candidate chunk{searchResults.length !== 1 ? "s" : ""} in authorized tenant index:
                  </div>
                  {searchResults.length > 0 && searchViewMode === "json" && (
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(JSON.stringify(searchResults, null, 2));
                        setCopiedJson(true);
                        setTimeout(() => setCopiedJson(false), 2000);
                      }}
                      className="nav-tab-btn"
                      style={{ padding: "4px 10px", fontSize: "0.74rem" }}
                    >
                      {copiedJson ? <Check size={12} color="var(--brand-emerald)" /> : <Copy size={12} />}
                      {copiedJson ? "Copied JSON" : "Copy Full JSON"}
                    </button>
                  )}
                </div>

                {searchResults.length === 0 ? (
                  <div style={{ fontSize: "0.84rem", color: "var(--text-secondary)", fontStyle: "italic", padding: "16px", background: "rgba(15, 23, 42, 0.5)", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                    No matching chunks found for this query in the authorized tenant index.
                  </div>
                ) : searchViewMode === "json" ? (
                  <div
                    style={{
                      background: "rgba(2, 6, 23, 0.9)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "8px",
                      padding: "16px",
                      maxHeight: "550px",
                      overflowY: "auto",
                      fontFamily: "var(--font-mono, monospace)",
                      fontSize: "0.76rem",
                      color: "#94a3b8",
                      lineHeight: 1.5,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {JSON.stringify(searchResults, null, 2)}
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                    {searchResults.map((res: any, i: number) => {
                      const docTitle =
                        res.source?.document_title ||
                        res.document_title ||
                        res.source?.filename ||
                        res.filename ||
                        "Indexed Document";
                      const filename = res.source?.filename || res.filename;
                      const chunkIndex = res.source?.chunk_index !== undefined ? res.source.chunk_index : i;
                      const pageNum = res.source?.page_number;
                      const heading = res.source?.section_heading;
                      const hierarchy = Array.isArray(res.source?.heading_hierarchy) ? res.source.heading_hierarchy : [];
                      const chunkType = res.source?.chunk_type || "text";
                      const isExpanded = expandedChunks[i] ?? true;

                      return (
                        <div
                          key={res.chunk_id || i}
                          style={{
                            padding: "16px",
                            background: "rgba(15, 23, 42, 0.95)",
                            border: "1px solid var(--border-subtle)",
                            borderRadius: "10px",
                            fontSize: "0.84rem",
                            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.25)",
                          }}
                        >
                          {/* Card Header */}
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px", flexWrap: "wrap", gap: "8px" }}>
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                                <strong style={{ color: "#fff", fontSize: "0.92rem" }}>
                                  {docTitle}
                                </strong>
                                {filename && filename !== docTitle && (
                                  <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                                    ({filename})
                                  </span>
                                )}
                                <span
                                  style={{
                                    fontSize: "0.70rem",
                                    padding: "2px 7px",
                                    borderRadius: "4px",
                                    background: "rgba(99, 102, 241, 0.15)",
                                    border: "1px solid rgba(99, 102, 241, 0.3)",
                                    color: "var(--brand-indigo)",
                                    fontWeight: 600,
                                  }}
                                >
                                  Chunk #{chunkIndex}
                                </span>
                                {pageNum !== null && pageNum !== undefined && (
                                  <span
                                    style={{
                                      fontSize: "0.70rem",
                                      padding: "2px 7px",
                                      borderRadius: "4px",
                                      background: "rgba(255, 255, 255, 0.07)",
                                      color: "var(--text-secondary)",
                                    }}
                                  >
                                    Page {pageNum}
                                  </span>
                                )}
                                <span
                                  style={{
                                    fontSize: "0.70rem",
                                    padding: "2px 7px",
                                    borderRadius: "4px",
                                    background: "rgba(6, 182, 212, 0.1)",
                                    color: "var(--brand-cyan)",
                                    textTransform: "uppercase",
                                    letterSpacing: "0.03em",
                                  }}
                                >
                                  {chunkType}
                                </span>
                              </div>

                              {/* Heading Hierarchy Breadcrumbs */}
                              {(hierarchy.length > 0 || heading) && (
                                <div
                                  style={{
                                    fontSize: "0.75rem",
                                    color: "var(--brand-cyan)",
                                    marginTop: "5px",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "5px",
                                    flexWrap: "wrap",
                                  }}
                                >
                                  <Layers size={11} />
                                  <span>
                                    {hierarchy.length > 0
                                      ? hierarchy.join("  ›  ")
                                      : heading}
                                  </span>
                                </div>
                              )}
                            </div>

                            {/* Copy Full Chunk Button */}
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(res.content || "");
                                  setCopiedChunkIdx(i);
                                  setTimeout(() => setCopiedChunkIdx(null), 2000);
                                }}
                                className="nav-tab-btn"
                                style={{ padding: "3px 8px", fontSize: "0.72rem" }}
                                title="Copy full chunk content to clipboard"
                              >
                                {copiedChunkIdx === i ? (
                                  <Check size={11} color="var(--brand-emerald)" />
                                ) : (
                                  <Copy size={11} />
                                )}
                                {copiedChunkIdx === i ? "Copied" : "Copy"}
                              </button>
                            </div>
                          </div>

                          {/* Full Retrieval Scores & Telemetry Row */}
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "10px",
                              flexWrap: "wrap",
                              padding: "6px 10px",
                              background: "rgba(0, 0, 0, 0.3)",
                              borderRadius: "6px",
                              border: "1px solid rgba(255, 255, 255, 0.05)",
                            }}
                          >
                            {res.rrf_score !== undefined && (
                              <span className="telemetry-badge telemetry-badge-emerald" style={{ fontSize: "0.72rem" }}>
                                <span className="telemetry-label">RRF Score:</span> {(res.rrf_score * 100).toFixed(2)}%
                              </span>
                            )}
                            {res.rerank_score !== undefined && res.rerank_score !== null && (
                              <span className="telemetry-badge telemetry-badge-cyan" style={{ fontSize: "0.72rem" }}>
                                <span className="telemetry-label">Rerank Score:</span> {(res.rerank_score * 100).toFixed(2)}%
                              </span>
                            )}
                            {res.dense_rank !== undefined && res.dense_rank !== null && (
                              <span className="telemetry-badge telemetry-badge-indigo" style={{ fontSize: "0.72rem" }}>
                                <span className="telemetry-label">Dense Rank:</span> #{res.dense_rank}
                              </span>
                            )}
                            {res.sparse_rank !== undefined && res.sparse_rank !== null && (
                              <span className="telemetry-badge telemetry-badge-amber" style={{ fontSize: "0.72rem" }}>
                                <span className="telemetry-label">Sparse Rank:</span> #{res.sparse_rank}
                              </span>
                            )}
                            {res.chunk_id && (
                              <span
                                style={{
                                  fontSize: "0.68rem",
                                  color: "var(--text-muted)",
                                  fontFamily: "monospace",
                                  marginLeft: "auto",
                                }}
                                title={`Chunk UUID: ${res.chunk_id}`}
                              >
                                ID: {String(res.chunk_id).slice(0, 8)}...
                              </span>
                            )}
                          </div>

                          {/* Full Chunk Content (Uncut & Un-truncated) */}
                          <div
                            style={{
                              padding: "12px 14px",
                              background: "rgba(2, 6, 23, 0.8)",
                              border: "1px solid rgba(255, 255, 255, 0.08)",
                              borderRadius: "6px",
                              fontFamily: "var(--font-mono, monospace)",
                              fontSize: "0.79rem",
                              lineHeight: 1.6,
                              color: "#e2e8f0",
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-word",
                              maxHeight: isExpanded ? "420px" : "120px",
                              overflowY: "auto",
                            }}
                          >
                            {res.content || "Empty content payload."}
                          </div>

                          {/* Toggle Expand / Collapse for long chunks */}
                          {res.content && res.content.length > 350 && (
                            <div style={{ marginTop: "6px", display: "flex", justifyContent: "flex-end" }}>
                              <button
                                onClick={() =>
                                  setExpandedChunks((prev) => ({ ...prev, [i]: !isExpanded }))
                                }
                                style={{
                                  background: "transparent",
                                  border: "none",
                                  color: "var(--brand-indigo)",
                                  cursor: "pointer",
                                  fontSize: "0.72rem",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  padding: "2px 6px",
                                }}
                              >
                                {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                                {isExpanded ? "Collapse Content" : "Show Full Content"}
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
