"use client";
import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { conversations, documents } from "@/lib/api";
import type { Document, Conversation } from "@/lib/api";

interface Props {
  courseId: string;
  courseName: string;
  onClose: () => void;
  onCreated: (conv: Conversation) => void;
}

export default function NewConvModal({ courseId, courseName, onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [docs, setDocs] = useState<Document[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    documents.list(courseId).then(setDocs).catch(() => {});
  }, [courseId]);

  const toggleDoc = (id: string) => {
    setSelectedDocs(prev => prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id]);
  };

  const create = async () => {
    const n = name.trim();
    if (!n) return;
    setLoading(true);
    try {
      const conv = await conversations.create(n, courseId, selectedDocs.length ? selectedDocs : undefined);
      onCreated(conv);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "1rem" }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="fade-in" style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, padding: "1.5rem", width: "100%", maxWidth: 420 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>New conversation</h3>
            <p style={{ margin: "0.2rem 0 0", fontSize: "0.8rem", color: "var(--text-3)" }}>in {courseName}</p>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", display: "flex", borderRadius: 8, padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-2)", marginBottom: "0.4rem", letterSpacing: "0.04em", textTransform: "uppercase" }}>Name</label>
          <input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && create()}
            placeholder="e.g. Chapter 3 review"
            style={{ width: "100%", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 9, padding: "0.6rem 0.8rem", color: "var(--text)", fontSize: "0.88rem", outline: "none", fontFamily: "inherit" }}
            onFocus={e => (e.target.style.borderColor = "var(--accent)")}
            onBlur={e => (e.target.style.borderColor = "var(--border)")}
          />
        </div>

        {docs.length > 0 && (
          <div style={{ marginBottom: "1.25rem" }}>
            <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--text-2)", marginBottom: "0.5rem", letterSpacing: "0.04em", textTransform: "uppercase" }}>Filter documents (optional)</label>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", maxHeight: 160, overflowY: "auto" }}>
              {docs.map(doc => (
                <label key={doc.id} style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", padding: "0.35rem 0.5rem", borderRadius: 7, background: selectedDocs.includes(doc.id) ? "var(--accent-glow)" : "transparent", transition: "background 0.1s" }}>
                  <input type="checkbox" checked={selectedDocs.includes(doc.id)} onChange={() => toggleDoc(doc.id)} style={{ accentColor: "var(--accent)", width: 14, height: 14 }} />
                  <span style={{ fontSize: "0.82rem", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.name}</span>
                </label>
              ))}
            </div>
            {selectedDocs.length === 0 && <p style={{ margin: "0.4rem 0 0", fontSize: "0.75rem", color: "var(--text-3)" }}>No filter = search all documents in this course</p>}
          </div>
        )}

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={onClose} style={{ flex: 1, background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 9, padding: "0.6rem", fontSize: "0.88rem", cursor: "pointer", color: "var(--text-2)", fontFamily: "inherit" }}>
            Cancel
          </button>
          <button
            onClick={create}
            disabled={!name.trim() || loading}
            style={{ flex: 1, background: !name.trim() ? "var(--border)" : "var(--accent)", border: "none", borderRadius: 9, padding: "0.6rem", fontSize: "0.88rem", fontWeight: 500, cursor: !name.trim() ? "not-allowed" : "pointer", color: !name.trim() ? "var(--text-3)" : "#fff", fontFamily: "inherit", transition: "background 0.15s" }}
          >
            {loading ? "Creating…" : "Start chat"}
          </button>
        </div>
      </div>
    </div>
  );
}
