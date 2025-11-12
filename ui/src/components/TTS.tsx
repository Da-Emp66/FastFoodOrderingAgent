import { useState } from "react";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";

export default function TTS() {
  const {
    voices, voiceURI, setVoiceURI,
    rate, setRate,
    pitch, setPitch,
    speaking, speak, stop
  } = useSpeechSynthesis();

  const [text, setText] = useState("Hi Jose! This is a basic text to speech test.");

  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", padding: "1rem", display: "grid", gap: "1rem" }}>
      <h1>🔊 Text to Speech</h1>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Voice</span>
        <select value={voiceURI} onChange={(e) => setVoiceURI(e.target.value)}>
          {voices.map(v => (
            <option key={v.voiceURI} value={v.voiceURI}>
              {v.name}
            </option>
          ))}
        </select>
      </label>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Rate</span>
        <input type="range" min={0.5} max={1.5} step={0.05} value={rate}
               onChange={(e) => setRate(parseFloat(e.target.value))}/>
      </label>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Pitch</span>
        <input type="range" min={0.5} max={2} step={0.05} value={pitch}
               onChange={(e) => setPitch(parseFloat(e.target.value))}/>
      </label>

      <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} />

      <div style={{ display: "flex", gap: ".75rem" }}>
        <button onClick={() => speak(text)} disabled={speaking}>Speak</button>
        <button onClick={stop} disabled={!speaking}>Stop</button>
      </div>
    </div>
  );
}
