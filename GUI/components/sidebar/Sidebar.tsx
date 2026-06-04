"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import {
  BookOpen, ChevronRight, ChevronDown, Plus, Upload, Trash2,
  MessageSquare, LogOut, GraduationCap, FileText, RefreshCw, X
} from "lucide-react";
import { courses, documents, conversations, tasks } from "@/lib/api";
import type { Course, Document, Conversation, TaskStatus, UploadTaskInfo } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ThemeToggle from "@/components/ThemeToggle";

interface DocWithStatus extends Document {
  task_id?: string;
  taskStatus?: TaskStatus["status"];
}

interface Props {
  activeConvId: string | null;
  onSelectConv: (id: string) => void;
  onNewConv: (courseId: string, courseName: string) => void;
  refreshSignal?: number;
}

function StatusDot({ status }: { status?: TaskStatus["status"] }) {
  if (!status) return null;
  const cls = status.toLowerCase();
  return <span className={`status-dot ${cls}`} title={status} />;
}

function CourseRow({
  course, activeConvId, onSelectConv, onNewConv, onDeleteCourse, refreshSignal,
}: {
  course: Course;
  activeConvId: string | null;
  onSelectConv: (id: string) => void;
  onNewConv: (courseId: string, courseName: string) => void;
  onDeleteCourse: (id: string) => void;
  refreshSignal?: number;
}) {
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState<DocWithStatus[]>([]);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const d = await documents.list(course.id);
      setDocs(prev => d.map((doc: Document) => {
        const existing = prev.find(p => p.id === doc.id);
        return { ...doc, task_id: existing?.task_id, taskStatus: existing?.taskStatus };
      }));
    } catch {/* ignore */}
  }, [course.id]);

  const loadConvs = useCallback(async () => {
    try {
      const all = await conversations.list();
      setConvs(all);
    } catch {/* ignore */}
  }, []);

  // Load on open
  useEffect(() => {
    if (open) { loadDocs(); loadConvs(); }
  }, [open, loadDocs, loadConvs]);

  // Re-fetch convs whenever a new one is created (refreshSignal bumped by parent)
  useEffect(() => {
    if (open && refreshSignal) loadConvs();
  }, [refreshSignal, open, loadConvs]);

  useEffect(() => {
    const pending = docs.filter(d => d.task_id && d.taskStatus !== "SUCCESS" && d.taskStatus !== "FAILURE");
    if (pending.length === 0) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      const updates = await Promise.all(
        pending.map(d => tasks.status(d.task_id!).then(s => ({ id: d.id, status: s.status })).catch(() => null))
      );
      setDocs(prev => prev.map(d => {
        const u = updates.find(u => u?.id === d.id);
        return u ? { ...d, taskStatus: u.status } : d;
      }));
    }, 2500);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [docs]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      const res: UploadTaskInfo[] = await documents.upload(course.id, files);
      setDocs(prev => {
        const newDocs = res.map(t => ({ id: t.id, name: t.name, task_id: t.task_id, taskStatus: "PENDING" as TaskStatus["status"] }));
        return [...prev, ...newDocs];
      });
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    await documents.delete(course.id, docId);
    setDocs(prev => prev.filter(d => d.id !== docId));
  };

  const handleDeleteConv = async (convId: string) => {
    await conversations.delete(convId);
    setConvs(prev => prev.filter(c => c.id !== convId));
  };

  return (
    <div style={{ marginBottom: "0.15rem" }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.45rem 0.6rem", borderRadius: 8, cursor: "pointer", transition: "background 0.1s", userSelect: "none" }}
        onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-3)")}
        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
      >
        <span style={{ color: "var(--text-3)", flexShrink: 0, transition: "transform 0.15s", transform: open ? "rotate(0deg)" : "rotate(-90deg)" }}>
          <ChevronDown size={13} />
        </span>
        <GraduationCap size={14} color="var(--accent)" style={{ flexShrink: 0 }} />
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.82rem", fontWeight: 500, color: "var(--text)" }}>{course.name}</span>
        <button
          onClick={e => { e.stopPropagation(); onDeleteCourse(course.id); }}
          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: 2, display: "flex", borderRadius: 4, opacity: 0, transition: "opacity 0.1s" }}
          className="delete-btn"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {open && (
        <div style={{ paddingLeft: "1.4rem" }}>
          {/* Documents */}
          <div style={{ marginBottom: "0.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.3rem 0.4rem", marginBottom: "0.2rem" }}>
              <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--text-3)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Documents</span>
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent)", padding: 2, display: "flex", borderRadius: 4 }}
                title="Upload documents"
              >
                {uploading ? <RefreshCw size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Upload size={12} />}
              </button>
              <input ref={fileRef} type="file" multiple accept=".pdf,.txt" onChange={handleUpload} style={{ display: "none" }} />
            </div>
            {docs.length === 0 && (
              <p style={{ fontSize: "0.75rem", color: "var(--text-3)", padding: "0.2rem 0.4rem", margin: 0, fontStyle: "italic" }}>No documents yet</p>
            )}
            {docs.map(doc => (
              <div key={doc.id}
                style={{ display: "flex", alignItems: "center", gap: "0.4rem", padding: "0.3rem 0.4rem", borderRadius: 6, marginBottom: "0.1rem" }}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-3)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <FileText size={12} color="var(--text-3)" style={{ flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: "0.78rem", color: "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.name}</span>
                <StatusDot status={doc.taskStatus} />
                <button onClick={() => handleDeleteDoc(doc.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: 1, display: "flex", borderRadius: 3, flexShrink: 0 }}>
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>

          {/* Chats */}
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.3rem 0.4rem", marginBottom: "0.2rem" }}>
              <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--text-3)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Chats</span>
              <button
                onClick={() => onNewConv(course.id, course.name)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent)", padding: 2, display: "flex", borderRadius: 4 }}
                title="New conversation"
              >
                <Plus size={12} />
              </button>
            </div>
            {convs.length === 0 && (
              <p style={{ fontSize: "0.75rem", color: "var(--text-3)", padding: "0.2rem 0.4rem", margin: 0, fontStyle: "italic" }}>No chats yet</p>
            )}
            {convs.map(conv => (
              <div
                key={conv.id}
                onClick={() => onSelectConv(conv.id)}
                style={{ display: "flex", alignItems: "center", gap: "0.4rem", padding: "0.3rem 0.4rem", borderRadius: 6, marginBottom: "0.1rem", cursor: "pointer", background: activeConvId === conv.id ? "var(--accent-glow)" : "transparent", transition: "background 0.1s" }}
                onMouseEnter={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = "var(--bg-3)"; }}
                onMouseLeave={e => { if (activeConvId !== conv.id) e.currentTarget.style.background = "transparent"; }}
              >
                <MessageSquare size={12} color={activeConvId === conv.id ? "var(--accent)" : "var(--text-3)"} style={{ flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: "0.78rem", color: activeConvId === conv.id ? "var(--accent)" : "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{conv.name}</span>
                <button onClick={e => { e.stopPropagation(); handleDeleteConv(conv.id); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: 1, display: "flex", borderRadius: 3, flexShrink: 0 }}>
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        div:hover .delete-btn { opacity: 1 !important; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

export default function Sidebar({ activeConvId, onSelectConv, onNewConv, refreshSignal }: Props) {
  const { user, logout } = useAuth();
  const [courseList, setCourseList] = useState<Course[]>([]);
  const [newCourseName, setNewCourseName] = useState("");
  const [addingCourse, setAddingCourse] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    courses.list().then(setCourseList).catch(() => {});
  }, []);

  useEffect(() => {
    if (addingCourse) inputRef.current?.focus();
  }, [addingCourse]);

  const createCourse = async () => {
    const name = newCourseName.trim();
    if (!name) return;
    try {
      const c = await courses.create(name);
      setCourseList(prev => [...prev, c]);
      setNewCourseName("");
      setAddingCourse(false);
    } catch (err) {
      console.error(err);
    }
  };

  const deleteCourse = async (id: string) => {
    try {
      await courses.delete(id);
      setCourseList(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <aside style={{ width: 260, minWidth: 260, height: "100vh", background: "var(--surface)", borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "1rem 0.9rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.6rem", flexShrink: 0 }}>
        <div style={{ width: 32, height: 32, background: "var(--accent-glow)", border: "1px solid var(--border)", borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <BookOpen size={16} color="var(--accent)" />
        </div>
        <span style={{ fontWeight: 600, fontSize: "0.95rem", letterSpacing: "-0.02em", flex: 1 }}>UniRAG</span>
        <ThemeToggle size={15} />
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "0.75rem 0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.2rem 0.6rem 0.5rem" }}>
          <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-3)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Courses</span>
          <button onClick={() => setAddingCourse(true)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent)", padding: 2, display: "flex", borderRadius: 4 }} title="New course">
            <Plus size={14} />
          </button>
        </div>

        {addingCourse && (
          <div style={{ padding: "0 0.5rem 0.5rem", display: "flex", gap: "0.3rem" }}>
            <input
              ref={inputRef}
              value={newCourseName}
              onChange={e => setNewCourseName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") createCourse(); if (e.key === "Escape") { setAddingCourse(false); setNewCourseName(""); } }}
              placeholder="Course name…"
              style={{ flex: 1, background: "var(--bg-2)", border: "1px solid var(--accent)", borderRadius: 7, padding: "0.4rem 0.6rem", color: "var(--text)", fontSize: "0.8rem", outline: "none", fontFamily: "inherit" }}
            />
            <button onClick={createCourse} style={{ background: "var(--accent)", border: "none", borderRadius: 7, padding: "0 0.5rem", cursor: "pointer", color: "#fff", display: "flex", alignItems: "center" }}>
              <ChevronRight size={14} />
            </button>
          </div>
        )}

        {courseList.length === 0 && !addingCourse && (
          <p style={{ fontSize: "0.78rem", color: "var(--text-3)", padding: "0.5rem 0.8rem", fontStyle: "italic" }}>No courses yet. Create one above.</p>
        )}
        {courseList.map(course => (
          <CourseRow
            key={course.id}
            course={course}
            activeConvId={activeConvId}
            onSelectConv={onSelectConv}
            onNewConv={onNewConv}
            onDeleteCourse={deleteCourse}
            refreshSignal={refreshSignal}
          />
        ))}
      </div>

      <div style={{ borderTop: "1px solid var(--border)", padding: "0.75rem 0.9rem", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--accent-glow)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--accent)" }}>
              {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "?"}
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ margin: 0, fontSize: "0.8rem", fontWeight: 500, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user?.full_name || "User"}</p>
            <p style={{ margin: 0, fontSize: "0.7rem", color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user?.email}</p>
          </div>
          <button onClick={logout} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)", padding: 4, display: "flex", borderRadius: 6 }} title="Logout">
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
