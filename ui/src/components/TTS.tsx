import { useEffect, useMemo, useRef, useState } from "react";

type VoiceOption = SpeechSynthesisVoice;

export default function TTS() {
  const [text, setText] = useState("Hi Jose! This is a basic text-to-speech test running in your React app on Ubuntu.");
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [voiceURI, setVoiceURI] = useState<string>("");
  const [rate, setRate] = useState(1.0);
  const [pitch, setPitch] = useState(1);
  const [speaking, setSpeaking] = useState(false);
  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Load voices (Chrome loads them async)
  useEffect(() => {
    const synth = window.speechSynthesis;
    const load = () => {
      const v = synth.getVoices().sort((a, b) => a.name.localeCompare(b.name));
      setVoices(v);
      if (!voiceURI && v.length) setVoiceURI(v[0].voiceURI);
    };
    load();
    window.speechSynthesis.onvoiceschanged = load;
    return () => { window.speechSynthesis.onvoiceschanged = null; };
  }, [voiceURI]);

  const selectedVoice = useMemo(
    () => voices.find(v => v.voiceURI === voiceURI),
    [voices, voiceURI]
  );

  const stop = () => {
    window.speechSynthesis.cancel();
    setSpeaking(false);
    utterRef.current = null;
  };

  const speak = (delay = 1000) => {
    if (!("speechSynthesis" in window)) {
      alert("This browser does not support speechSynthesis. Try Chromium/Chrome.");
      return;
    }
    if (!text.trim()) return;
    stop(); // cancel any prior speech

    const u = new SpeechSynthesisUtterance(text);
    if (selectedVoice) u.voice = selectedVoice;
    u.rate = rate;
    u.pitch = pitch;

    u.onstart = () => setSpeaking(true);
    u.onend = () => { setSpeaking(false); utterRef.current = null; };
    u.onerror = () => { setSpeaking(false); utterRef.current = null; };

    utterRef.current = u;
    setTimeout(() => {
      window.speechSynthesis.speak(u);
    }, delay);
  };

  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", padding: "1rem", display: "grid", gap: "1rem" }}>
      <h1>🔊 Text-to-Speech (Browser)</h1>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Voice</span>
        <select value={voiceURI} onChange={(e) => setVoiceURI(e.target.value)}>
          {voices.map(v => (
            <option key={v.voiceURI} value={v.voiceURI}>
              {v.name} {v.lang ? `(${v.lang})` : ""} {v.default ? "• default" : ""}
            </option>
          ))}
        </select>
      </label>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Rate: {rate.toFixed(2)}</span>
        <input type="range" min={0.5} max={1.5} step={0.05} value={rate}
               onChange={(e) => setRate(parseFloat(e.target.value))}/>
      </label>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Pitch: {pitch.toFixed(2)}</span>
        <input type="range" min={0.5} max={2} step={0.05} value={pitch}
               onChange={(e) => setPitch(parseFloat(e.target.value))}/>
      </label>

      <label style={{ display: "grid", gap: ".5rem" }}>
        <span>Text</span>
        <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} />
      </label>

      <div style={{ display: "flex", gap: ".75rem" }}>
        <button onClick={speak} disabled={speaking}>▶️ Speak</button>
        <button onClick={stop} disabled={!speaking}>⏹ Stop</button>
      </div>

      {!voices.length && (
        <p style={{ color: "#888" }}>
          No voices loaded yet. If using Chromium, give it a second or reload the page.
        </p>
      )}
    </div>
  );
}
