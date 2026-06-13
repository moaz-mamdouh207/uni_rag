const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const auth = {
  register: (data: { email: string; password: string; full_name: string }) =>
    request(
      "/auth/register",
      { method: "POST", body: JSON.stringify(data) }
    ),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; refresh_token: string; expires_in: number }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify(data) }
    ),

  me: () =>
    request<{ id: string; email: string; full_name: string; role: string }>(
      "/auth/me"
    ),

  logout: (refresh_token: string) =>
    request(
      "/auth/logout",
      { method: "POST", body: JSON.stringify({ refresh_token }) }
    ),
};

// ── Courses ───────────────────────────────────────────────────────────────────
export interface Course { id: string; name: string }

export const courses = {
  list: () =>
    request<Course[]>("/knowledge/courses"),

  create: (name: string) =>
    request<Course>("/knowledge/courses", { method: "POST", body: JSON.stringify({ name }) }),

  delete: (id: string) =>
    request(`/knowledge/courses/${id}`, { method: "DELETE" }),
};

// ── Documents ─────────────────────────────────────────────────────────────────
export interface Document { id: string; name: string }
export interface UploadTaskInfo { id: string; name: string; task_id: string }

// Matches the server's AttachmentType enum values
export type AttachmentType = "pdf" | "image/png" | "image/jpeg" | "image/webp";

export interface Attachment {
  id: string;       // UUID
  type: AttachmentType;
}

export const documents = {
  list: (courseId: string) =>
    request<Document[]>(`/knowledge/courses/${courseId}/documents`),

  upload: async (courseId: string, files: File[]): Promise<UploadTaskInfo[]> => {
    const token = getToken();
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const res = await fetch(`${BASE_URL}/knowledge/courses/${courseId}/documents`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Upload failed");
    }
    return res.json();
  },

  /**
   * Upload temporary attachments scoped to a conversation.
   * POST /chat/conversations/{conversationId}/messages/attachments
   * Returns Attachment[] — each with `id` (UUID) and `type` (AttachmentType).
   */
  uploadTemp: async (conversationId: string, files: File[]): Promise<Attachment[]> => {
    const token = getToken();
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const res = await fetch(
      `${BASE_URL}/chat/conversations/${conversationId}/messages/attachments`,
      {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Temp upload failed");
    }
    return res.json(); // Attachment[]
  },

  delete: (courseId: string, documentId: string) =>
    request(`/knowledge/courses/${courseId}/documents/${documentId}`, { method: "DELETE" }),
};

// ── Tasks ─────────────────────────────────────────────────────────────────────
export interface TaskStatus {
  task_id: string;
  status: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY" | "REVOKED";
  result?: Record<string, unknown>;
  error?: string;
}

export const tasks = {
  status: (taskId: string) => request<TaskStatus>(`/tasks/${taskId}`),
};

// ── Conversations ─────────────────────────────────────────────────────────────
export interface Conversation { id: string; name: string }

export const conversations = {
  list: () => request<Conversation[]>("/chat/conversations"),

  create: (name: string, course_id: string, documents_ids?: string[]) =>
    request<Conversation>("/chat/conversations", {
      method: "POST",
      body: JSON.stringify({ name, meta: { course_id, documents_ids: documents_ids ?? null } }),
    }),

  delete: (id: string) =>
    request(`/chat/conversations/${id}`, { method: "DELETE" }),

  update: (id: string, name: string) =>
    request<Conversation>(`/chat/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
};

// ── Messages ──────────────────────────────────────────────────────────────────
export interface Message { role: "user" | "assistant" | "system"; content: string }

// A single cited source returned alongside the answer.
// `index` corresponds to the bracketed marker (e.g. "2" for "[2]") that
// appears inline in `answer`.
export interface CitedSource {
  index: string;
  reason: string;
  document_id: string;
  starting_page: number;
  end_page: number;
}

export interface ChatResponse {
  answer: string;
  sources: CitedSource[];
}

export const chat = {
  /**
   * GET /chat/conversations/{conversationId}/messages
   * Returns Message[] directly.
   */
  history: (conversationId: string) =>
    request<Message[]>(`/chat/conversations/${conversationId}/messages`),

  /**
   * POST /chat/conversations/{conversationId}/messages
   * Body: { query, attachments, stream }
   */
  send: (conversationId: string, query: string, attachments?: Attachment[]) =>
    request<ChatResponse>(`/chat/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        query,
        attachments: attachments && attachments.length > 0 ? attachments : null,
        stream: false,
      }),
    }),
};