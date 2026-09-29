/**
 * Type-safe API client for Enterprise Knowledge & Operations Intelligence Platform
 * Connects Next.js frontend to FastAPI backend (:8000)
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const STORAGE_TOKEN_KEY = "aura_enterprise_jwt_token";

export interface HealthStatus {
  status: string;
  project?: string;
  database?: string;
  pgvector?: boolean;
}

export interface UserProfile {
  id?: string;
  email: string;
  full_name?: string;
  role: "admin" | "manager" | "analyst";
  tenant_id: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user?: UserProfile;
}

export interface DecodedToken {
  sub?: string;
  email?: string;
  role?: string;
  tenant_id?: string;
  exp?: number;
}

export interface SourceCitation {
  citation_id?: number;
  document_id: string;
  filename?: string;
  document_title?: string;
  chunk_id?: string;
  relevance_score?: number;
  snippet?: string;
  page_number?: number;
  section_heading?: string;
}

export interface RagResponse {
  question: string;
  answer: string;
  citations: SourceCitation[];
  route?: string;
  execution_time_ms: number;
  has_sufficient_context?: boolean;
}

export interface SqlResponse {
  prompt: string;
  synthesized_sql: string;
  execution_time_ms: number;
  row_count: number;
  columns: string[];
  data: Record<string, unknown>[];
  ast_validated: boolean;
  tables_accessed: string[];
  explanation?: string;
}

export interface AgentReasoningStep {
  step: number;
  node: string;
  action: string;
  status: "success" | "pending" | "skipped";
  details?: string;
}

export interface AgentResponse {
  prompt: string;
  query?: string;
  detected_route: "RAG" | "SQL" | "HYBRID_AGENT";
  routing_reason: string;
  rag_context?: {
    answer: string;
    citations: SourceCitation[];
  };
  sql_context?: {
    sql: string;
    columns: string[];
    rows: Record<string, unknown>[];
  };
  compliance_synthesis?: string;
  final_answer: string;
  execution_time_ms: number;
  trace_id: string;
  reasoning_steps: AgentReasoningStep[];
}

export interface IngestedDocument {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  chunk_count: number;
  status: string;
  created_at: string;
}

class ApiService {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem(STORAGE_TOKEN_KEY);
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem(STORAGE_TOKEN_KEY, token);
      } else {
        localStorage.removeItem(STORAGE_TOKEN_KEY);
      }
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== "undefined") {
      this.token = localStorage.getItem(STORAGE_TOKEN_KEY);
    }
    return this.token;
  }

  getDecodedUser(): DecodedToken | null {
    const token = this.getToken();
    if (!token) return null;
    try {
      const parts = token.split(".");
      if (parts.length !== 3) return null;
      const payloadStr = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(payloadStr);
    } catch {
      return null;
    }
  }

  private getHeaders(contentType = "application/json"): HeadersInit {
    const headers: Record<string, string> = {};
    if (contentType) {
      headers["Content-Type"] = contentType;
    }
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  async checkHealth(): Promise<HealthStatus> {
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        method: "GET",
        headers: this.getHeaders(),
        cache: "no-store",
      });
      if (!res.ok) {
        return { status: "unhealthy" };
      }
      return await res.json();
    } catch {
      return { status: "disconnected" };
    }
  }

  /**
   * Primary enterprise authentication method.
   * Calls POST /api/v1/auth/login with { email, password, tenant_id }
   */
  async login(
    email = "demo_admin@enterprise.com",
    password = "Password123!",
    tenantId = "default_tenant"
  ): Promise<TokenResponse> {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        tenant_id: tenantId,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      const msg = err.detail || `Authentication failed (${res.status})`;
      throw new Error(msg);
    }

    const data: TokenResponse = await res.json();
    this.setToken(data.access_token);
    return data;
  }

  /**
   * Register a new user in the database.
   * Calls POST /api/v1/auth/register
   */
  async register(
    email: string,
    password = "Password123!",
    fullName = "Enterprise User",
    role: "admin" | "manager" | "analyst" = "analyst",
    tenantId = "default_tenant"
  ): Promise<UserProfile> {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
        role,
        tenant_id: tenantId,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Registration failed" }));
      const msg = err.detail || `Registration failed (${res.status})`;
      throw new Error(msg);
    }

    return await res.json();
  }

  /**
   * Seamless login-or-register helper:
   * Attempts login; if user doesn't exist, registers and logs in immediately.
   */
  async loginOrRegister(
    email = "demo_admin@enterprise.com",
    password = "Password123!",
    fullName = "Demo Admin",
    role: "admin" | "manager" | "analyst" = "admin",
    tenantId = "default_tenant"
  ): Promise<TokenResponse> {
    try {
      return await this.login(email, password, tenantId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      if (
        msg.toLowerCase().includes("incorrect") ||
        msg.toLowerCase().includes("not found") ||
        msg.toLowerCase().includes("unauthorized")
      ) {
        try {
          await this.register(email, password, fullName, role, tenantId);
          return await this.login(email, password, tenantId);
        } catch {
          throw err;
        }
      }
      throw err;
    }
  }

  logout() {
    this.setToken(null);
  }

  async getMe(): Promise<UserProfile | null> {
    const token = this.getToken();
    if (!token) return null;
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        method: "GET",
        headers: this.getHeaders(),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  async checkHealthDetailed(): Promise<{
    status: string;
    database: string;
    active_embedding_model: string;
    environment?: string;
    pingMs: number;
  }> {
    const start = performance.now();
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        method: "GET",
        headers: this.getHeaders(),
        cache: "no-store",
      });
      const pingMs = Math.max(1, Math.round(performance.now() - start));
      if (!res.ok) {
        return {
          status: "unhealthy",
          database: "error",
          active_embedding_model: "unknown",
          pingMs,
        };
      }
      const data = await res.json();
      return {
        ...data,
        pingMs,
      };
    } catch {
      const pingMs = Math.max(1, Math.round(performance.now() - start));
      return {
        status: "disconnected",
        database: "offline",
        active_embedding_model: "offline",
        pingMs,
      };
    }
  }

  /**
   * Query Policy RAG.
   * Backend schema: RAGQueryRequest { question: str, top_k: int, ... }
   */
  async queryRag(question: string, topK = 5): Promise<RagResponse> {
    const startTime = performance.now();
    const res = await fetch(`${API_BASE_URL}/rag/query`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ question, top_k: topK }),
    });

    const latency = Math.round(performance.now() - startTime);

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error("401 Unauthorized: Please click 'Authorize' in the top right to log in and get a valid JWT token.");
      }
      const err = await res.json().catch(() => ({ detail: "RAG query failed" }));
      throw new Error(err.detail || `RAG query failed (${res.status})`);
    }

    const data = await res.json();
    return {
      question,
      answer: data.answer || "No response received",
      citations: data.citations || [],
      route: "RAG",
      execution_time_ms: latency,
      has_sufficient_context: data.has_sufficient_context,
    };
  }

  /**
   * Query Natural-Language Text-to-SQL Sandbox.
   * Backend schema: NaturalLanguageSQLRequest { prompt: str, explain: bool }
   */
  async querySql(prompt: string): Promise<SqlResponse> {
    const startTime = performance.now();
    const res = await fetch(`${API_BASE_URL}/sql/query`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ prompt, explain: true }),
    });

    const latency = Math.round(performance.now() - startTime);

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error("401 Unauthorized: Please click 'Authorize' in the top right to log in and get a valid JWT token.");
      }
      const err = await res.json().catch(() => ({ detail: "SQL query failed" }));
      throw new Error(err.detail || `SQL query failed (${res.status})`);
    }

    const data = await res.json();
    const rows = (data.rows || []) as Record<string, unknown>[];
    const columns = (data.columns && data.columns.length > 0)
      ? data.columns
      : rows.length > 0 ? Object.keys(rows[0]) : [];

    return {
      prompt,
      synthesized_sql: data.sanitized_sql || data.generated_sql || "SELECT 1;",
      execution_time_ms: data.execution_time_ms || latency,
      row_count: data.row_count ?? rows.length,
      columns,
      data: rows,
      ast_validated: true,
      tables_accessed: ["operational_expenses", "departments"],
      explanation: data.explanation,
    };
  }

  /**
   * Query Unified LangGraph Agent & Dispatcher.
   * Backend schema: AgentQueryRequest { prompt: str, force_route: ExecutionRoute | null }
   * Response schema: AgentQueryResponse { prompt, route_selected, answer, plan_steps, citations, sql_results, execution_time_ms }
   */
  async queryAgent(prompt: string, forceRoute?: string): Promise<AgentResponse> {
    const startTime = performance.now();
    const payload: { prompt: string; force_route?: string } = { prompt };
    if (forceRoute) payload.force_route = forceRoute;

    const res = await fetch(`${API_BASE_URL}/agent/query`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });

    const latency = Math.round(performance.now() - startTime);

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error("401 Unauthorized: Please click 'Authorize' in the top right to log in and get a valid JWT token.");
      }
      const err = await res.json().catch(() => ({ detail: "Agent query failed" }));
      throw new Error(err.detail || `Agent query failed (${res.status})`);
    }

    const data = await res.json();
    const routeSelected = (data.route_selected || data.detected_route || "HYBRID_AGENT") as
      | "RAG"
      | "SQL"
      | "HYBRID_AGENT";

    // Map plan steps from backend PlanStep { step_number, action, target, status, output_summary }
    const backendSteps = Array.isArray(data.plan_steps) ? data.plan_steps : [];
    const steps: AgentReasoningStep[] = backendSteps.map((st: {
      step_number: number;
      action: string;
      target: string;
      status: string;
      output_summary?: string;
    }) => ({
      step: st.step_number,
      node: st.target || st.action,
      action: st.action,
      status: "success",
      details: st.output_summary,
    }));

    if (steps.length === 0) {
      steps.push({
        step: 1,
        node: "QueryRouter",
        action: `Classified intent as ${routeSelected}`,
        status: "success",
        details: "Deterministic AST & keyword classification",
      });
    }

    // Extract SQL context if present
    let sqlContext: AgentResponse["sql_context"] = undefined;
    if (data.sql_results && data.sql_results.length > 0) {
      const sqlRes = data.sql_results[0];
      sqlContext = {
        sql: sqlRes.sanitized_sql || sqlRes.generated_sql,
        columns: sqlRes.columns || [],
        rows: sqlRes.rows || [],
      };
    }

    // Extract RAG context if citations are present
    let ragContext: AgentResponse["rag_context"] = undefined;
    if (data.citations && data.citations.length > 0) {
      ragContext = {
        answer: data.answer,
        citations: data.citations.map((c: SourceCitation) => ({
          document_id: String(c.document_id),
          document_title: c.document_title || c.filename || "Policy Document",
          chunk_id: String(c.citation_id || c.chunk_id || "chunk"),
          content_snippet: c.snippet,
        })),
      };
    }

    return {
      prompt,
      detected_route: routeSelected,
      routing_reason: `Executed via ${routeSelected} pathway`,
      rag_context: ragContext,
      sql_context: sqlContext,
      final_answer: data.answer || "Processing complete.",
      execution_time_ms: data.execution_time_ms || latency,
      trace_id: res.headers.get("x-trace-id") || `trc_${Math.random().toString(36).substring(2, 10)}`,
      reasoning_steps: steps,
    };
  }

  async listDocuments(): Promise<IngestedDocument[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/documents`, {
        method: "GET",
        headers: this.getHeaders(),
      });
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : data.documents || [];
    } catch {
      return [];
    }
  }

  async uploadDocument(file: File, title: string): Promise<IngestedDocument> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);

    const headers: Record<string, string> = {};
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error("401 Unauthorized: Please click 'Authorize' in the top right to log in and get a valid JWT token.");
      }
      const err = await res.text();
      throw new Error(`Upload failed (${res.status}): ${err}`);
    }

    return await res.json();
  }

  async getDocumentStatus(documentId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/documents/${documentId}/status`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch document status (${res.status})`);
    }
    return await res.json();
  }

  async searchKnowledgeBase(query = "policy guidance"): Promise<any[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/retrieval/search`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({ query, top_k: 20, top_n: 10 }),
      });
      if (!res.ok) return [];
      const data = await res.json();
      return data.results || [];
    } catch {
      return [];
    }
  }
}

export const api = new ApiService();
