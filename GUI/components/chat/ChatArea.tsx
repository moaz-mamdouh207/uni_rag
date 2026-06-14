"use client";
import { useState, useEffect, useRef, useCallback, Fragment } from "react";
import { Send, Bot, User, Sparkles, BookOpen, Paperclip, X, FileText, Image as ImageIcon, File } from "lucide-react";
import { chat, conversations, documents, courses } from "@/lib/api";
import type { Message, Conversation, Attachment, CitedSource, PageImageItem, Document } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface Props {
  conversationId: string | null;
}

interface AttachedFile {
  file: File;
  attachment?: Attachment;   // id + type returned by the server
  uploading: boolean;
  error?: string;
}

// Local message shape — augments the API Message with optional citation sources
// returned alongside an assistant answer.
interface DisplayMessage extends Message {
  sources?: CitedSource[];
}

function fileIcon(file: File) {
  if (file.type.startsWith("image/")) return <ImageIcon size={13} />;
  if (file.type === "application/pdf" || file.name.endsWith(".pdf")) return <FileText size={13} />;
  return <File size={13} />;
}

function AttachmentPill({ af, onRemove }: { af: AttachedFile; onRemove: () => void }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: "0.35rem",
      background: af.error ? "rgba(192,57,43,0.1)" : "var(--bg-3)",
      border: `1px solid ${af.error ? "rgba(192,57,43,0.3)" : "var(--border)"}`,
      borderRadius: 7, padding: "0.25rem 0.45rem", fontSize: "0.75rem",
      color: af.error ? "var(--danger)" : "var(--text-2)", maxWidth: 180, flexShrink: 0,
    }}>
      <span style={{ color: af.error ? "var(--danger)" : "var(--accent)", display: "flex" }}>
        {fileIcon(af.file)}
      </span>
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
        {af.uploading ? "Uploading…" : af.error ? "Failed" : af.file.name}
      </span>
      {!af.uploading && (
        <button onClick={onRemove} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: 0, display: "flex", lineHeight: 1 }}>
          <X size={11} />
        </button>
      )}
    </div>
  );
}

// Renders a single [n] citation marker with a hover tooltip showing the
// agent's reason for the citation plus the source document and page range.
function CitationMarker({
  source, label, docNames, docCourses,
}: {
  source?: CitedSource;
  label: string;
  docNames: Record<string, string>;
  docCourses: Record<string, string>;
}) {
  const [hovered, setHovered] = useState(false);
  const [pages, setPages] = useState<PageImageItem[] | null>(null);
  const [loadingPages, setLoadingPages] = useState(false);
  const [pagesError, setPagesError] = useState<string | null>(null);
  const [activePage, setActivePage] = useState(0);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelHide = () => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  };

  const scheduleHide = () => {
    cancelHide();
    hideTimerRef.current = setTimeout(() => setHovered(false), 400);
  };

  useEffect(() => {
    return () => cancelHide();
  }, []);

  if (!source) {
    // No matching source for this index — render as plain text.
    return <sup>[{label}]</sup>;
  }

  const pageRange = source.starting_page === source.end_page
    ? `Page ${source.starting_page}`
    : `Pages ${source.starting_page}–${source.end_page}`;

  const docLabel = docNames[source.document_id] || `${source.document_id.slice(0, 8)}…`;
  const courseId = docCourses[source.document_id];

  const [modalOpen, setModalOpen] = useState(false);

  const handleViewPages = async () => {
    if (pages) {
      setModalOpen(true);
      return;
    }
    if (!courseId || loadingPages) return;
    setLoadingPages(true);
    setPagesError(null);
    try {
      const res = await documents.getPages(courseId, source.document_id, source.starting_page, source.end_page);
      setPages(res.pages);
      setActivePage(0);
      setModalOpen(true);
    } catch (err) {
      setPagesError(err instanceof Error ? err.message : "Failed to load pages");
    } finally {
      setLoadingPages(false);
    }
  };

  const closePages = () => {
    setModalOpen(false);
  };

  const showingPages = modalOpen && pages && pages.length > 0;

  return (
    <span
      style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={() => { cancelHide(); setHovered(true); }}
      onMouseLeave={scheduleHide}
    >
      <sup
        style={{
          display: "inline-block",
          fontSize: "0.7em",
          fontWeight: 600,
          color: "var(--accent)",
          background: "var(--accent-glow)",
          border: "1px solid rgba(193, 127, 58, 0.3)",
          borderRadius: 4,
          padding: "0 0.3em",
          margin: "0 0.1em",
          cursor: "default",
          lineHeight: 1.4,
          verticalAlign: "super",
        }}
      >
        [{source.index.replace(/[[\]]/g, "")}]
      </sup>
      {hovered && (
        <span
          onMouseEnter={cancelHide}
          onMouseLeave={scheduleHide}
          style={{
            position: "absolute",
            bottom: "100%",
            left: "50%",
            transform: "translateX(-50%)",
            width: 300,
            maxWidth: "92vw",
            maxHeight: 420,
            overflowY: "auto",
            background: "var(--surface)",
            border: "1px solid var(--border-2)",
            borderRadius: 10,
            boxShadow: "0 6px 20px rgba(0, 0, 0, 0.18)",
            padding: "0.8rem 0.9rem 0.9rem",
            marginBottom: 6,
            zIndex: 50,
            fontSize: "0.95rem",
            lineHeight: 1.6,
            whiteSpace: "normal",
            textAlign: "left",
          }}
        >
          {/* Reason stays visible at all times */}
          <span style={{ display: "block", color: "var(--text)", marginBottom: "0.5rem" }}>
            {source.reason}
          </span>

          <span
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "0.5rem",
              color: "var(--text-3)",
              fontSize: "0.82rem",
              fontWeight: 600,
              letterSpacing: "0.02em",
              borderTop: "1px solid var(--border)",
              paddingTop: "0.4rem",
              marginBottom: loadingPages || pagesError ? "0.6rem" : 0,
            }}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {docLabel} · {pageRange}
            </span>
            <button
              onClick={handleViewPages}
              disabled={loadingPages || !courseId}
              style={{
                flexShrink: 0,
                fontSize: "0.82rem",
                fontWeight: 600,
                color: "#fff",
                background: "var(--accent)",
                border: "none",
                borderRadius: 6,
                padding: "0.35rem 0.7rem",
                cursor: loadingPages || !courseId ? "not-allowed" : "pointer",
                opacity: loadingPages || !courseId ? 0.6 : 1,
              }}
            >
              {loadingPages ? "Loading…" : pages ? "View pages" : "View pages"}
            </button>
          </span>

          {pagesError && (
            <span style={{ display: "block", color: "var(--danger)", fontSize: "0.85rem" }}>
              {pagesError}
            </span>
          )}
        </span>
      )}

      {showingPages && pages && (
        <span
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "2rem",
          }}
          onClick={closePages}
        >
          <span
            onClick={e => e.stopPropagation()}
            style={{
              position: "relative",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              width: "min(900px, 92vw)",
              maxHeight: "92vh",
              background: "var(--surface)",
              border: "1px solid var(--border-2)",
              borderRadius: 12,
              boxShadow: "0 12px 40px rgba(0,0,0,0.35)",
              padding: "1.25rem",
              fontSize: "0.95rem",
              lineHeight: 1.6,
            }}
          >
            {/* Close button */}
            <button
              onClick={closePages}
              title="Close"
              style={{
                position: "absolute",
                top: 10,
                right: 10,
                zIndex: 2,
                width: 32,
                height: 32,
                borderRadius: "50%",
                border: "none",
                background: "rgba(0,0,0,0.55)",
                color: "#fff",
                fontSize: "1.1rem",
                lineHeight: 1,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              ×
            </button>

            <span style={{ display: "block", fontSize: "0.85rem", color: "var(--text-3)", marginBottom: "0.5rem" }}>
              {docLabel} · Page {pages[activePage].page_number}
            </span>

            {/* Image stage with prev/next arrows */}
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.75rem", width: "100%", flex: 1, minHeight: 0 }}>
              <button
                onClick={() => setActivePage(p => Math.max(0, p - 1))}
                disabled={activePage === 0}
                style={{
                  flexShrink: 0,
                  width: 40,
                  height: 40,
                  borderRadius: "50%",
                  border: "1px solid var(--border)",
                  background: "var(--bg-2)",
                  color: "var(--text)",
                  fontSize: "1.3rem",
                  cursor: activePage === 0 ? "not-allowed" : "pointer",
                  opacity: activePage === 0 ? 0.4 : 1,
                }}
              >
                ‹
              </button>

              <span style={{ flex: 1, minHeight: 0, display: "flex", justifyContent: "center", overflow: "hidden" }}>
                <img
                  src={`data:image/png;base64,${pages[activePage].image}`}
                  alt={`Page ${pages[activePage].page_number}`}
                  style={{ maxWidth: "100%", maxHeight: "65vh", objectFit: "contain", borderRadius: 6, border: "1px solid var(--border)", display: "block" }}
                />
              </span>

              <button
                onClick={() => setActivePage(p => Math.min(pages!.length - 1, p + 1))}
                disabled={activePage === pages.length - 1}
                style={{
                  flexShrink: 0,
                  width: 40,
                  height: 40,
                  borderRadius: "50%",
                  border: "1px solid var(--border)",
                  background: "var(--bg-2)",
                  color: "var(--text)",
                  fontSize: "1.3rem",
                  cursor: activePage === pages.length - 1 ? "not-allowed" : "pointer",
                  opacity: activePage === pages.length - 1 ? 0.4 : 1,
                }}
              >
                ›
              </button>
            </span>

            {/* Reason — kept at the bottom, above the dots */}
            <span style={{ display: "block", color: "var(--text)", textAlign: "center", marginTop: "1rem", padding: "0 1rem" }}>
              {source.reason}
            </span>

            {/* Dot indicators */}
            {pages.length > 1 && (
              <span style={{ display: "flex", justifyContent: "center", gap: "0.4rem", marginTop: "0.75rem" }}>
                {pages.map((p, idx) => (
                  <button
                    key={p.page_number}
                    onClick={() => setActivePage(idx)}
                    title={`Page ${p.page_number}`}
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      background: idx === activePage ? "var(--text)" : "var(--border-2)",
                    }}
                  />
                ))}
              </span>
            )}
          </span>
        </span>
      )}
    </span>
  );
}

// Splits message content on [n] markers and interleaves rendered markdown
// segments with CitationMarker components.
function renderMessageContent(content: string, sources: CitedSource[] | undefined, docNames: Record<string, string>, docCourses: Record<string, string>) {
  const sourceMap = new Map<string, CitedSource>();
  (sources || []).forEach(s => sourceMap.set(s.index.replace(/[[\]]/g, ""), s));

  const citationRegex = /\[(\d+)\]/g;
  const parts: { text: string; citation?: string }[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = citationRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: content.slice(lastIndex, match.index) });
    }
    parts.push({ text: "", citation: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push({ text: content.slice(lastIndex) });
  }

  // If there are no citations at all, render the whole thing as one markdown block.
  if (!parts.some(p => p.citation)) {
    return (
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {content}
      </ReactMarkdown>
    );
  }

  return (
    <span>
      {parts.map((p, i) => {
        if (p.citation) {
          const src = sourceMap.get(p.citation);
          return <CitationMarker key={i} source={src} label={p.citation} docNames={docNames} docCourses={docCourses} />;
        }
        if (!p.text) return null;
        return (
          <ReactMarkdown
            key={i}
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            // Render inline-ish: paragraphs become spans via component override
            components={{
              p: ({ children }) => <Fragment>{children}</Fragment>,
            }}
          >
            {p.text}
          </ReactMarkdown>
        );
      })}
    </span>
  );
}

function MessageBubble({ msg, isLast, docNames, docCourses }: { msg: DisplayMessage; isLast: boolean; docNames: Record<string, string>; docCourses: Record<string, string> }) {
  const isUser = msg.role === "user";
  return (
    <div
      className={isLast ? "fade-in" : ""}
      style={{ display: "flex", gap: "0.85rem", padding: "0.75rem 0", alignItems: "flex-start" }}
    >
      <div style={{ width: 30, height: 30, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: isUser ? "var(--accent-glow)" : "var(--bg-3)", border: "1px solid var(--border)", marginTop: 2 }}>
        {isUser ? <User size={14} color="var(--accent)" /> : <Bot size={14} color="var(--text-2)" />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontSize: "0.75rem", fontWeight: 600, color: isUser ? "var(--accent)" : "var(--text-3)", letterSpacing: "0.04em", textTransform: "uppercase", display: "block", marginBottom: "0.3rem" }}>
          {isUser ? "You" : "UniRAG"}
        </span>
        <div className="message-body" style={{ color: "var(--text)", lineHeight: 1.7, wordBreak: "break-word" }}>
          {isUser
            ? <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{msg.content}</ReactMarkdown>
            : renderMessageContent(msg.content, msg.sources, docNames, docCourses)}
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: "0.85rem", padding: "0.75rem 0", alignItems: "flex-start" }} className="fade-in">
      <div style={{ width: 30, height: 30, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-3)", border: "1px solid var(--border)", marginTop: 2 }}>
        <Bot size={14} color="var(--text-2)" />
      </div>
      <div style={{ paddingTop: "0.6rem", display: "flex", gap: "4px", alignItems: "center" }}>
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}

function LoadingHistory() {
  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 24, height: 24, border: "2px solid var(--border)", borderTop: "2px solid var(--accent)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem", padding: "4rem 2rem", textAlign: "center" }}>
      <div style={{ width: 56, height: 56, borderRadius: 16, background: "var(--accent-glow)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Sparkles size={24} color="var(--accent)" />
      </div>
      <div>
        <h3 style={{ margin: "0 0 0.3rem", fontSize: "1rem", fontWeight: 600, color: "var(--text)" }}>Ask anything about your courses</h3>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-3)", maxWidth: 320 }}>
          This conversation has no messages yet. Type a question below to get started.
        </p>
      </div>
    </div>
  );
}

function NoConvSelected() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem", padding: "4rem 2rem", textAlign: "center" }}>
      <div style={{ width: 56, height: 56, borderRadius: 16, background: "var(--bg-3)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <BookOpen size={24} color="var(--text-3)" />
      </div>
      <div>
        <h3 style={{ margin: "0 0 0.3rem", fontSize: "1rem", fontWeight: 500, color: "var(--text-2)" }}>No conversation selected</h3>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-3)" }}>Pick a chat from the sidebar or create a new one.</p>
      </div>
    </div>
  );
}

export default function ChatArea({ conversationId }: Props) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [convName, setConvName] = useState("");
  const [docNames, setDocNames] = useState<Record<string, string>>({});
  const [docCourses, setDocCourses] = useState<Record<string, string>>({});
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Build a document_id -> name map (used to label citation tooltips) by
  // reusing the same course/document endpoints the sidebar uses.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const courseList = await courses.list();
        const lists = await Promise.all(
          courseList.map(c => documents.list(c.id).then(docs => ({ courseId: c.id, docs })).catch(() => ({ courseId: c.id, docs: [] as Document[] })))
        );
        if (cancelled) return;
        const nameMap: Record<string, string> = {};
        const courseMap: Record<string, string> = {};
        lists.forEach(({ courseId, docs }) => {
          docs.forEach(d => { nameMap[d.id] = d.name; courseMap[d.id] = courseId; });
        });
        setDocNames(nameMap);
        setDocCourses(courseMap);
      } catch {/* ignore */}
    })();
    return () => { cancelled = true; };
  }, []);

  const loadHistory = useCallback(async (id: string) => {
    setLoadingHistory(true);
    try {
      const res = await chat.history(id);
      setMessages(res.filter((m: Message) => m.role !== "system"));
    } catch {
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (conversationId) {
      setMessages([]);
      setConvName("");
      setAttachedFiles([]);
      loadHistory(conversationId);
      conversations.list().then((all: Conversation[]) => {
        const c = all.find(c => c.id === conversationId);
        if (c) setConvName(c.name);
      }).catch(() => {});
    }
  }, [conversationId, loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const autoResize = () => {
    const t = textareaRef.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 160) + "px";
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!conversationId) return;
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    if (fileInputRef.current) fileInputRef.current.value = "";

    const placeholders: AttachedFile[] = files.map(f => ({ file: f, uploading: true }));
    setAttachedFiles(prev => [...prev, ...placeholders]);

    try {
      // Upload against the current conversation; returns Attachment[] with id + type
      const attachments = await documents.uploadTemp(conversationId, files);
      setAttachedFiles(prev => {
        const updated = [...prev];
        const startIdx = updated.length - placeholders.length;
        attachments.forEach((attachment, i) => {
          updated[startIdx + i] = { ...updated[startIdx + i], uploading: false, attachment };
        });
        return updated;
      });
    } catch (err) {
      setAttachedFiles(prev => {
        const updated = [...prev];
        const startIdx = updated.length - placeholders.length;
        for (let i = startIdx; i < updated.length; i++) {
          updated[i] = { ...updated[i], uploading: false, error: err instanceof Error ? err.message : "Upload failed" };
        }
        return updated;
      });
    }
  };

  const removeAttachment = (idx: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const anyUploading = attachedFiles.some(f => f.uploading);

  // Collect successfully uploaded Attachment objects to send with the message
  const readyAttachments: Attachment[] = attachedFiles
    .filter(f => f.attachment && !f.error)
    .map(f => f.attachment as Attachment);

  const send = async () => {
    const query = input.trim();
    if (!query || !conversationId || sending || anyUploading) return;

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setSending(true);
    setAttachedFiles([]);

    setMessages(prev => [...prev, { role: "user", content: query }]);

    try {
      const res = await chat.send(
        conversationId,
        query,
        readyAttachments.length ? readyAttachments : undefined,
      );
      setMessages(prev => [...prev, { role: "assistant", content: res.answer, sources: res.sources }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Something went wrong"}` }]);
    } finally {
      setSending(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const canSend = !!input.trim() && !sending && !anyUploading;

  const renderContent = () => {
    if (!conversationId) return <NoConvSelected />;
    if (loadingHistory) return <LoadingHistory />;
    return (
      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", paddingTop: "1rem" }}>
        {messages.length === 0 && !sending && <EmptyState />}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} isLast={i === messages.length - 1} docNames={docNames} docCourses={docCourses} />
        ))}
        {sending && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    );
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--bg)" }}>
      {/* Header */}
      {conversationId && (
        <div style={{ padding: "0.85rem 1.5rem", borderBottom: "1px solid var(--border)", background: "var(--surface)", flexShrink: 0, display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--success)" }} />
          <span style={{ fontSize: "0.9rem", fontWeight: 500, color: "var(--text)" }}>{convName || "Conversation"}</span>
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 1.5rem" }}>
        {renderContent()}
      </div>

      {/* Input */}
      {conversationId && (
        <div style={{ padding: "1rem 1.5rem 1.25rem", flexShrink: 0, background: "var(--bg)" }}>
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            {attachedFiles.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.5rem" }}>
                {attachedFiles.map((af, i) => (
                  <AttachmentPill key={i} af={af} onRemove={() => removeAttachment(i)} />
                ))}
              </div>
            )}

            <div
              style={{ display: "flex", gap: "0.6rem", alignItems: "flex-end", background: "var(--surface)", border: "1px solid var(--border-2)", borderRadius: 14, padding: "0.6rem", transition: "border-color 0.15s, box-shadow 0.15s" }}
              onFocusCapture={e => { const p = e.currentTarget; p.style.borderColor = "var(--accent)"; p.style.boxShadow = "0 0 0 3px var(--accent-glow)"; }}
              onBlurCapture={e => { const p = e.currentTarget; p.style.borderColor = "var(--border-2)"; p.style.boxShadow = "none"; }}
            >
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={sending}
                title="Attach files"
                style={{ width: 34, height: 34, borderRadius: 9, background: "none", border: "none", cursor: sending ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, color: "var(--text-3)", transition: "color 0.15s, background 0.15s", padding: 0 }}
                onMouseEnter={e => { if (!sending) { (e.currentTarget as HTMLButtonElement).style.color = "var(--accent)"; (e.currentTarget as HTMLButtonElement).style.background = "var(--accent-glow)"; } }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-3)"; (e.currentTarget as HTMLButtonElement).style.background = "none"; }}
              >
                <Paperclip size={16} />
              </button>

              <input ref={fileInputRef} type="file" multiple style={{ display: "none" }} onChange={handleFileChange} />

              <textarea
                ref={textareaRef}
                value={input}
                onChange={e => { setInput(e.target.value); autoResize(); }}
                onKeyDown={handleKey}
                placeholder="Ask a question about your documents…"
                disabled={sending}
                rows={1}
                style={{ flex: 1, background: "none", border: "none", outline: "none", resize: "none", color: "var(--text)", fontSize: "0.9rem", lineHeight: 1.6, fontFamily: "inherit", padding: "0.25rem 0", minHeight: 24, maxHeight: 160 }}
              />

              <button
                onClick={send}
                disabled={!canSend}
                title={anyUploading ? "Waiting for uploads…" : "Send"}
                style={{ width: 34, height: 34, borderRadius: 9, background: !canSend ? "var(--bg-3)" : "var(--accent)", border: "none", cursor: !canSend ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.15s" }}
              >
                <Send size={15} color={!canSend ? "var(--text-3)" : "#fff"} />
              </button>
            </div>

            <p style={{ textAlign: "center", fontSize: "0.7rem", color: "var(--text-3)", margin: "0.5rem 0 0" }}>
              Press Enter to send · Shift+Enter for newline · <Paperclip size={10} style={{ display: "inline", verticalAlign: "middle" }} /> to attach files
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
