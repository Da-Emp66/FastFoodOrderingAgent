// ui/src/services/tts.ts

const baseUrl = import.meta.env.VITE_TTS_URL || "http://localhost:5055";

export async function playCoquiTTS(text: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!res.ok) throw new Error(`TTS API error: ${res.statusText}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await audio.play();
    return true;
  } catch (err) {
    console.error("Coqui TTS failed:", err);
    return false;
  }
}
