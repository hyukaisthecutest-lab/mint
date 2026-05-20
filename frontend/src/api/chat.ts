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
}

export async function fetchHistory(): Promise<ChatMessage[]> {
  const res = await client.get("/chat/history");
  return res.data.history;
}

export async function clearHistory(): Promise<void> {
  await client.delete("/chat/history");
}

export async function sendMessage(
  message: string,
  voiceMode: boolean,
  traceId: string
): Promise<ChatResponse> {
  const res = await client.post(
    "/chat",
    { message, voice_mode: voiceMode },
    { headers: { "X-Trace-ID": traceId } }
  );
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
