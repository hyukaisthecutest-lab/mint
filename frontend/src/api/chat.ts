import client from "./client";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  text: string;
  audio: string | null;
  trace_id: string;
  elapsed_ms: number;
  queued?: boolean;
}

export async function fetchHistory(): Promise<ChatMessage[]> {
  const res = await client.get("/chat/history");
  return res.data.history;
}

export async function clearHistory(): Promise<void> {
  await client.delete("/chat/history");
}

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollChatStatus(
  jobId: string,
  traceId: string
): Promise<ChatResponse> {
  while (true) {
    await sleep(3000);
    const res = await client.get(`/chat/status/${jobId}`);
    const { status, text, audio, error } = res.data;
    if (status === "done") {
      return { text, audio: audio ?? null, trace_id: traceId, elapsed_ms: 0 };
    }
    if (status === "error") {
      throw new Error(error || "Agent failed while queued");
    }
    // status === "pending" — keep polling
  }
}

export async function sendMessage(
  message: string,
  voiceMode: boolean,
  traceId: string,
  onQueued?: () => void
): Promise<ChatResponse> {
  const res = await client.post(
    "/chat",
    { message, voice_mode: voiceMode },
    { headers: { "X-Trace-ID": traceId } }
  );

  if (res.status === 202) {
    onQueued?.();
    return pollChatStatus(res.data.job_id, traceId);
  }

  return res.data;
}

export async function transcribeAudio(blob: Blob, traceId: string): Promise<string> {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  const res = await client.post("/chat/transcribe", form, {
    headers: {
      "Content-Type": "multipart/form-data",
      "X-Trace-ID": traceId,
    },
  });
  return res.data.text;
}
