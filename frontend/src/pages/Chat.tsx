import { useState, useRef, useEffect } from "react";
import { Mic, MicOff, Send, Bot, User } from "lucide-react";
import { sendMessage, transcribeAudio, ChatMessage } from "../api/chat";
import { useAudioRecorder } from "../hooks/useAudioRecorder";

function newTraceId() {
  return crypto.randomUUID();
}

interface MessageWithMeta extends ChatMessage {
  traceId?: string;
  elapsedMs?: number;
}

function MessageBubble({ msg }: { msg: MessageWithMeta }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser ? "bg-mint-600" : "bg-gray-200"}`}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-gray-600" />}
      </div>
      <div>
        <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser ? "bg-mint-600 text-white rounded-tr-sm" : "bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm"
        }`}>
          {msg.content}
        </div>
        {!isUser && msg.elapsedMs && (
          <div className="flex items-center gap-3 mt-1 px-1">
            <span className="text-xs text-gray-400">{msg.elapsedMs}ms</span>
            {msg.traceId && (
              <span className="text-xs text-gray-300 font-mono" title="Trace ID">
                {msg.traceId.slice(0, 8)}…
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Chat() {
  const [history, setHistory] = useState<MessageWithMeta[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { recording, start, stop } = useAudioRecorder();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  const playAudio = (b64: string) => {
    const audio = new Audio(`data:audio/mp3;base64,${b64}`);
    audio.play();
  };

  const submit = async (message: string, isVoice: boolean) => {
    if (!message.trim()) return;
    const traceId = newTraceId();
    const userMsg: MessageWithMeta = { role: "user", content: message, traceId };
    setHistory((h) => [...h, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await sendMessage(message, history, isVoice, traceId);
      const assistantMsg: MessageWithMeta = {
        role: "assistant",
        content: res.text,
        traceId: res.trace_id,
        elapsedMs: res.elapsed_ms,
      };
      setHistory((h) => [...h, assistantMsg]);
      if (res.audio) playAudio(res.audio);
    } finally {
      setLoading(false);
    }
  };

  const handleMic = async () => {
    if (recording) {
      const blob = await stop();
      setTranscribing(true);
      try {
        const traceId = newTraceId();
        const text = await transcribeAudio(blob, traceId);
        setInput(text);
        setVoiceMode(true);
        await submit(text, true);
      } finally {
        setTranscribing(false);
        setVoiceMode(false);
      }
    } else {
      await start();
    }
  };

  const handleSend = () => {
    submit(input, false);
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="px-6 py-4 bg-white border-b border-gray-100 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-mint-600 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="font-semibold text-gray-900">Finance Assistant</p>
          <p className="text-xs text-gray-400">Ask about your spending, budget, and more</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {history.length === 0 && (
          <div className="text-center text-gray-400 mt-16">
            <Bot className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="font-medium">Hi! I'm your finance assistant.</p>
            <p className="text-sm mt-1">Type a question or click the mic to speak.</p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {[
                "What did I spend most on this month?",
                "How can I reduce my food costs?",
                "Am I over budget?",
                "Show my spending trend",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => submit(q, false)}
                  className="text-xs px-3 py-2 bg-white border border-gray-200 rounded-full hover:bg-mint-50 hover:border-mint-300 transition-colors text-gray-600"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {history.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {(loading || transcribing) && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-gray-600" />
            </div>
            <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1 items-center h-5">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="px-6 py-4 bg-white border-t border-gray-100">
        <div className="flex gap-3 items-end">
          <textarea
            className="flex-1 input resize-none"
            rows={1}
            placeholder={recording ? "🔴 Recording… click mic to stop" : "Ask about your finances…"}
            value={input}
            disabled={recording || transcribing}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <button
            onClick={handleMic}
            disabled={transcribing || loading}
            className={`p-2.5 rounded-lg transition-colors ${
              recording
                ? "bg-red-500 hover:bg-red-600 text-white"
                : "bg-gray-100 hover:bg-gray-200 text-gray-600"
            }`}
            title={recording ? "Stop recording" : "Speak"}
          >
            {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading || recording}
            className="btn-primary p-2.5"
            title="Send"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
