"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Sidebar from "@/components/sidebar/Sidebar";
import ChatArea from "@/components/chat/ChatArea";
import NewConvModal from "@/components/chat/NewConvModal";
import type { Conversation } from "@/lib/api";

export default function ChatPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [modal, setModal] = useState<{ courseId: string; courseName: string } | null>(null);
  // Bump this number every time a conversation is created — Sidebar watches it to refresh
  const [refreshSignal, setRefreshSignal] = useState(0);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "var(--bg)" }}>
        <div style={{ width: 32, height: 32, border: "2px solid var(--border)", borderTop: "2px solid var(--accent)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) return null;

  const handleConvCreated = (conv: Conversation) => {
    setActiveConvId(conv.id);
    setModal(null);
    // Signal the sidebar to re-fetch its conversation lists
    setRefreshSignal(prev => prev + 1);
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar
        activeConvId={activeConvId}
        onSelectConv={setActiveConvId}
        onNewConv={(courseId, courseName) => setModal({ courseId, courseName })}
        refreshSignal={refreshSignal}
      />
      <ChatArea conversationId={activeConvId} />

      {modal && (
        <NewConvModal
          courseId={modal.courseId}
          courseName={modal.courseName}
          onClose={() => setModal(null)}
          onCreated={handleConvCreated}
        />
      )}
    </div>
  );
}