import { useRef, useState } from "react";

const MIMES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

export const useRecorder = () => {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const rec = useRef(null);
  const chunks = useRef([]);
  const timer = useRef(null);

  const start = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MIMES.find((t) => window.MediaRecorder?.isTypeSupported?.(t));
    const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunks.current = [];
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
    r.start();
    rec.current = r;
    setSeconds(0);
    setRecording(true);
    timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
  };

  const stop = () => new Promise((resolve) => {
    const r = rec.current;
    if (!r) return resolve(null);
    r.onstop = () => {
      r.stream.getTracks().forEach((t) => t.stop());
      clearInterval(timer.current);
      rec.current = null;
      setRecording(false);
      resolve(new Blob(chunks.current, { type: r.mimeType || "audio/webm" }));
    };
    r.stop();
  });

  return { recording, seconds, start, stop };
};

export const blobName = (blob) => (blob.type.includes("mp4") ? "voice.m4a" : blob.type.includes("ogg") ? "voice.ogg" : "voice.webm");
export const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
