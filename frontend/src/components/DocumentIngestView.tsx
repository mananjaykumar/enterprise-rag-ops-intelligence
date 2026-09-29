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
  status: "ACTIVE_INDEXED" | "PENDING" | "PROCESSING";
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

          // Backend uses ACTIVE (not ACTIVE_INDEXED)
          const rawStatus = (d.status || "PENDING").toUpperCase();
          const mappedStatus: DocumentItem["status"] =
            rawStatus === "ACTIVE" ? "ACTIVE_INDEXED"
            : rawStatus === "PROCESSING" ? "PROCESSING"
            : "PENDING";

          return {
            id: String(d.id),
            title: d.title || d.filename,
            filename: d.filename,
            type: displayType,
            chunks: d.chunk_count ?? 0,
            status: mappedStatus,
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
                          <span
                            className={`audit-badge ${
                              doc.status === "ACTIVE_INDEXED"
                                ? "audit-badge-success"
                                : "audit-badge-pending"
                            }`}
                          >
                            <CheckCircle2 size={11} style={{ marginRight: "4px" }} />
                            {doc.status}
                          </span>
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
            <h3
              style={{
                fontSize: "0.96rem",
                fontWeight: 600,
                marginBottom: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <Search size={16} color="var(--brand-emerald)" />
              Live Knowledge Base Verification (Hybrid RAG Search)
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.84rem", marginBottom: "14px" }}>
              Test vector and full-text chunk retrieval on your authenticated tenant documents in real-time.
            </p>

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
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>
                  {searchResults.length} chunk{searchResults.length !== 1 ? "s" : ""} found in tenant index:
                </div>
                {searchResults.length === 0 ? (
                  <div style={{ fontSize: "0.84rem", color: "var(--text-secondary)", fontStyle: "italic" }}>
                    No matching chunks found for this query in the authorized tenant index.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {searchResults.slice(0, 3).map((res, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "12px 14px",
                          background: "rgba(15, 23, 42, 0.9)",
                          border: "1px solid var(--border-subtle)",
                          borderRadius: "8px",
                          fontSize: "0.82rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                          <strong style={{ color: "#fff" }}>
                            {res.document_title || res.filename || "Indexed Document"}
                          </strong>
                          {res.rrf_score && (
                            <span style={{ color: "var(--brand-emerald)", fontSize: "0.74rem" }}>
                              Score: {(res.rrf_score * 100).toFixed(2)}%
                            </span>
                          )}
                        </div>
                        <p style={{ color: "var(--text-secondary)", margin: 0, lineHeight: 1.5 }}>
                          {res.content ? res.content.slice(0, 200) + "..." : "Chunk content indexed."}
                        </p>
                      </div>
                    ))}
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
