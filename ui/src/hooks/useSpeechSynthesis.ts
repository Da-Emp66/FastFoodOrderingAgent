import { useEffect, useMemo, useRef, useState } from "react";

export function useSpeechSynthesis() {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceURI, setVoiceURI] = useState("");
  const [rate, setRate] = useState(1);
  const [pitch, setPitch] = useState(1);
  const [speaking, setSpeaking] = useState(false);

  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);

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

  const speak = (text: string) => {
    if (!("speechSynthesis" in window)) return;
    if (!text.trim()) return;

    stop();

    const u = new SpeechSynthesisUtterance(text);
    if (selectedVoice) u.voice = selectedVoice;
    u.rate = rate;
    u.pitch = pitch;

    u.onstart = () => setSpeaking(true);
    u.onend = () => { setSpeaking(false); utterRef.current = null; };
    u.onerror = () => { setSpeaking(false); utterRef.current = null; };

    utterRef.current = u;
    window.speechSynthesis.speak(u);
  };

  return {
    voices,
    voiceURI,
    setVoiceURI,
    rate,
    setRate,
    pitch,
    setPitch,
    speaking,
    speak,
    stop
  };
}
