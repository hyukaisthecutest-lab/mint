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

export async function sendMessage(
  message: string,
  history: ChatMessage[],
  voiceMode: boolean,
  traceId: string
): Promise<ChatResponse> {
  const res = await client.post(
    "/chat",
    { message, history, voice_mode: voiceMode },
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
