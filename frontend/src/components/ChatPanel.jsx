import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchConversations,
  createConversation,
  fetchConversation,
  deleteConversation,
  streamMessage,
  createOnboardingConversation,
  kickOnboarding,
  streamOnboardingMessage,
} from "../api";

// Tool names that modify job data — when these complete, notify parent to refresh
const JOB_MUTATING_TOOLS = new Set(["create_job"]);

function ChatPanel({ isOpen, onClose, onboarding = false, onOnboardingComplete, onJobsChanged }) {
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [expandedErrors, setExpandedErrors] = useState(new Set());
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Auto-resize textarea to fit content (up to ~8 lines)
  const autoResize = (el) => {
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 24;
    const maxHeight = lineHeight * 8;
    el.style.height = Math.min(el.scrollHeight, maxHeight) + "px";
  };

  useEffect(() => {
    autoResize(inputRef.current);
  }, [input]);

  useEffect(() => {
    if (isOpen && !onboarding) {
      loadConversations();
    }
  }, [isOpen]);

  // Onboarding auto-start: create conversation and kick the agent
  useEffect(() => {
    let cancelled = false;

    if (isOpen && onboarding && !currentConversation) {
      (async () => {
        try {
          const convo = await createOnboardingConversation();
          if (cancelled) return;
          setCurrentConversation(convo);
          setMessages([{ role: "assistant", content: "", segments: [] }]);
          setIsStreaming(true);

          let fullText = "";
          let segments = [];
          let currentTextIdx = -1;
          let onboardingDone = false;

          function pushUpdate() {
            if (cancelled) return;
            const snapshotSegments = segments.map((s) => ({ ...s }));
            setMessages([
              { role: "assistant", content: fullText, segments: snapshotSegments },
            ]);
          }

          const abortController = new AbortController();
          abortControllerRef.current = abortController;

          await kickOnboarding(convo.id, (event) => {
            if (cancelled) return;
            if (event.event === "error") {
              if (!fullText) {
                fullText = `Error: ${event.data.message}`;
                segments.push({ type: "text", content: fullText });
              }
              pushUpdate();
            } else if (event.event === "text_delta") {
              fullText += event.data.content;
              if (currentTextIdx >= 0 && segments[currentTextIdx].type === "text") {
                segments[currentTextIdx].content += event.data.content;
              } else {
                currentTextIdx = segments.length;
                segments.push({ type: "text", content: event.data.content });
              }
              pushUpdate();
            } else if (event.event === "tool_start") {
              currentTextIdx = -1;
              segments.push({ type: "tool", id: event.data.id, name: event.data.name, status: "running" });
              pushUpdate();
            } else if (event.event === "tool_result") {
              const idx = segments.findIndex((s) => s.type === "tool" && s.id === event.data.id);
              if (idx >= 0) segments[idx] = { ...segments[idx], status: "completed" };
              if (JOB_MUTATING_TOOLS.has(event.data.name) && onJobsChanged) onJobsChanged();
              pushUpdate();
            } else if (event.event === "tool_error") {
              const idx = segments.findIndex((s) => s.type === "tool" && s.id === event.data.id);
              if (idx >= 0) segments[idx] = { ...segments[idx], status: "error", error: event.data.error };
              pushUpdate();
            } else if (event.event === "onboarding_complete") {
              onboardingDone = true;
            } else if (event.event === "done") {
              pushUpdate();
            }
          }, { signal: abortController.signal });

          if (cancelled) return;
          abortControllerRef.current = null;
          setIsStreaming(false);
          if (onboardingDone && onOnboardingComplete) {
            onOnboardingComplete();
          }
        } catch (e) {
          if (e.name === "AbortError") {
            if (!cancelled) {
              abortControllerRef.current = null;
              setIsStreaming(false);
            }
            return;
          }
          console.error("Failed to start onboarding:", e);
          if (!cancelled) {
            abortControllerRef.current = null;
            setIsStreaming(false);
          }
        }
      })();
    }

    return () => {
      cancelled = true;
    };
  }, [isOpen, onboarding]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen && !isStreaming) {
      inputRef.current?.focus();
    }
  }, [isOpen, isStreaming, currentConversation]);

  async function loadConversations() {
    try {
      const data = await fetchConversations();
      setConversations(data);
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
  }

  async function selectConversation(id) {
    try {
      const data = await fetchConversation(id);
      setCurrentConversation(data);
      setMessages(data.messages || []);
    } catch (e) {
      console.error("Failed to load conversation:", e);
    }
  }

  async function handleNewChat() {
    try {
      const convo = await createConversation();
      setCurrentConversation(convo);
      setMessages([]);
      await loadConversations();
    } catch (e) {
      console.error("Failed to create conversation:", e);
    }
  }

  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }

  async function handleDeleteConversation(id, e) {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      if (currentConversation?.id === id) {
        setCurrentConversation(null);
        setMessages([]);
      }
      await loadConversations();
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  }

  async function handleSend() {
    if (!input.trim() || isStreaming) return;

    let convo = currentConversation;
    if (!convo) {
      convo = onboarding
        ? await createOnboardingConversation()
        : await createConversation();
      setCurrentConversation(convo);
    }

    const userMessage = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsStreaming(true);

    // Add placeholder for assistant response with segments array
    const assistantIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: "assistant", content: "", segments: [] }]);

    // Mutable tracking for the streaming callback
    let fullText = "";
    let segments = [];
    let currentTextIdx = -1;
    let onboardingDone = false;

    function pushUpdate() {
      const snapshotSegments = segments.map((s) => ({ ...s }));
      setMessages((prev) => {
        const updated = [...prev];
        updated[assistantIdx] = {
          ...updated[assistantIdx],
          content: fullText,
          segments: snapshotSegments,
        };
        return updated;
      });
    }

    const streamer = onboarding ? streamOnboardingMessage : streamMessage;
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      await streamer(convo.id, userMessage.content, (event) => {
        if (event.event === "text_delta") {
          fullText += event.data.content;
          // Append to current text segment, or create a new one
          if (currentTextIdx >= 0 && segments[currentTextIdx].type === "text") {
            segments[currentTextIdx].content += event.data.content;
          } else {
            currentTextIdx = segments.length;
            segments.push({ type: "text", content: event.data.content });
          }
          pushUpdate();
        } else if (event.event === "tool_start") {
          // End current text segment tracking so next text creates a new segment
          currentTextIdx = -1;
          segments.push({
            type: "tool",
            id: event.data.id,
            name: event.data.name,
            status: "running",
          });
          pushUpdate();
        } else if (event.event === "tool_result") {
          const idx = segments.findIndex((s) => s.type === "tool" && s.id === event.data.id);
          if (idx >= 0) {
            segments[idx] = { ...segments[idx], status: "completed" };
          }
          if (JOB_MUTATING_TOOLS.has(event.data.name) && onJobsChanged) onJobsChanged();
          pushUpdate();
        } else if (event.event === "tool_error") {
          const idx = segments.findIndex((s) => s.type === "tool" && s.id === event.data.id);
          if (idx >= 0) {
            segments[idx] = { ...segments[idx], status: "error", error: event.data.error };
          }
          pushUpdate();
        } else if (event.event === "done") {
          pushUpdate();
        } else if (event.event === "onboarding_complete") {
          onboardingDone = true;
        } else if (event.event === "error") {
          if (!fullText) {
            fullText = `Error: ${event.data.message}`;
            segments.push({ type: "text", content: fullText });
          }
          pushUpdate();
        }
      }, { signal: abortController.signal });
    } catch (e) {
      if (e.name === "AbortError") {
        // User cancelled — keep whatever content we have so far
        pushUpdate();
        abortControllerRef.current = null;
        setIsStreaming(false);
        return;
      }
      console.error("Stream error:", e);
      if (!fullText) {
        fullText = "Failed to get response. Check your API configuration.";
        segments.push({ type: "text", content: fullText });
      }
      pushUpdate();
    }

    abortControllerRef.current = null;
    setIsStreaming(false);
    if (onboardingDone && onOnboardingComplete) {
      onOnboardingComplete();
      return;
    }
    await loadConversations();
    setCurrentConversation((prev) => (prev ? { ...prev, title: input.trim().slice(0, 100) } : prev));
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-white shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
          <h2 className="font-semibold text-gray-900">
            {onboarding ? "Welcome! Let\u2019s set up your profile" : "AI Assistant"}
          </h2>
          <div className="flex gap-2">
            {!onboarding && (
              <>
                <button
                  onClick={handleNewChat}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  New Chat
                </button>
                <button
                  onClick={() => {
                    setCurrentConversation(null);
                    setMessages([]);
                  }}
                  className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                >
                  History
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="p-1 text-gray-500 hover:text-gray-700"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        {!currentConversation && !onboarding ? (
          /* Conversation list */
          <div className="flex-1 overflow-y-auto p-4">
            {conversations.length === 0 ? (
              <p className="text-gray-500 text-center mt-8">
                No conversations yet. Start a new chat!
              </p>
            ) : (
              <div className="space-y-2">
                {conversations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => selectConversation(c.id)}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-gray-50 cursor-pointer"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 truncate">{c.title}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(c.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDeleteConversation(c.id, e)}
                      className="ml-2 p-1 text-gray-400 hover:text-red-500"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Chat view */
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === "assistant" && msg.segments && msg.segments.length > 0 ? (
                    /* Render assistant segments in order */
                    msg.segments.map((seg, j) =>
                      seg.type === "text" ? (
                        <div key={j} className="flex justify-start mb-2">
                          <div className="max-w-[80%] rounded-lg px-4 py-2 bg-gray-100 text-gray-900">
                            <div className="markdown-body">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {seg.content}
                              </ReactMarkdown>
                            </div>
                          </div>
                        </div>
                      ) : seg.type === "tool" ? (
                        <div key={j} className="ml-2 mb-2">
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            {seg.status === "running" ? (
                              <span className="inline-block w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                            ) : seg.status === "completed" ? (
                              <span className="text-green-500">&#10003;</span>
                            ) : (
                              <span className="text-amber-500">&#9888;</span>
                            )}
                            <span className="font-mono">{seg.name}</span>
                            {seg.error && (
                              <button
                                onClick={() => setExpandedErrors((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(seg.id)) next.delete(seg.id);
                                  else next.add(seg.id);
                                  return next;
                                })}
                                className="text-gray-400 hover:text-gray-600 underline"
                              >
                                {expandedErrors.has(seg.id) ? "Hide details" : "Details"}
                              </button>
                            )}
                          </div>
                          {seg.error && expandedErrors.has(seg.id) && (
                            <div className="ml-5 mt-1 px-2 py-1 text-xs text-gray-500 bg-gray-50 rounded border border-gray-200 font-mono break-all">
                              {seg.error}
                            </div>
                          )}
                        </div>
                      ) : null
                    )
                  ) : (
                    /* User messages or assistant messages without segments (e.g. from history) */
                    <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-2 ${
                          msg.role === "user"
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-900"
                        }`}
                      >
                        {msg.role === "assistant" ? (
                          <div className="markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {isStreaming && messages[messages.length - 1]?.content === "" && (!messages[messages.length - 1]?.segments || messages[messages.length - 1].segments.length === 0) && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-lg px-4 py-2 flex items-center gap-1.5">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    <span className="ml-2 text-sm text-gray-500">Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t p-4">
              <div className="flex gap-2 items-end">
                <textarea
                  ref={inputRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder={onboarding ? "Tell me about yourself..." : "Ask about jobs..."}
                  disabled={isStreaming}
                  className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 resize-none leading-6"
                  style={{ maxHeight: "12rem" }}
                />
                {isStreaming ? (
                  <button
                    onClick={handleStop}
                    className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 flex items-center gap-1.5"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                      <rect x="6" y="6" width="12" height="12" rx="2" />
                    </svg>
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Send
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default ChatPanel;
