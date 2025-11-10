import { useState, useEffect, useRef } from "react";
import Typewriter from "./components/Typewriter";

export default function App() {
  const [listening, setListening] = useState(false);
  const [messages, setMessages] = useState([
    { sender: "ai", text: "👋 Hello! I'm Audient — your voice assistant." },
  ]);
  const [appLoaded, setAppLoaded] = useState(false);
  const chatRef = useRef(null);
  const [compactMode, setCompactMode] = useState(false);
  const [micIntensity, setMicIntensity] = useState(0);
  const [voiceSignatureEnabled, setVoiceSignatureEnabled] = useState(false);

  // 🔁 Keep reference to interval controller
  const wakeIntervalRef = useRef(null);
  const wakeLockedRef = useRef(false); // prevents overlapping wake-ups

  // ✅ Electron connection setup
  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      console.log("✅ Connected to Electron preload bridge");
      window.electron.ipcRenderer.send("ping-test");
      window.electron.ipcRenderer.on("window-position", (position) => {
        setCompactMode(position === "side");
      });
    }
    const timer = setTimeout(() => setAppLoaded(true), 300);
    return () => clearTimeout(timer);
  }, []);

  // 🧭 Auto-scroll messages
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTo({
        top: chatRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  // === 🎤 Passive wakeword polling ===
  useEffect(() => {
    async function checkWakeword() {
      if (wakeLockedRef.current) return; // ⛔ skip if wake session active

      try {
        const res = await fetch("http://127.0.0.1:5000/wakeword", { method: "POST" });
        const data = await res.json();

        if (data.wakeword_detected) {
          console.log("🎉 Wake word detected:", data.text);

          // 🔒 lock future wake polls
          wakeLockedRef.current = true;
          clearInterval(wakeIntervalRef.current);
          setListening(true);

          setMessages((prev) => [
            ...prev,
            { sender: "user", text: `🎤 (${data.text})` },
          ]);

          // 🎧 Trigger speech recognition after wakeup
          const listenRes = await fetch("http://127.0.0.1:5000/listen-voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              trigger: "wake",
              verify_voice: voiceSignatureEnabled,
            }),
          });

          const result = await listenRes.json();

          if (listenRes.ok) {
            setMessages((prev) => [
              ...prev,
              { sender: "user", text: result.text },
              { sender: "ai", text: result.reply },
            ]);

            // 🪄 Auto-dock window when opening apps/browsers
            if (
              result.action === "open_browser" ||
              result.action === "open_app" ||
              result.action === "compose_email"
            ) {
              window.electron?.ipcRenderer?.send("move-window-side");
              setCompactMode(true);
            }
          } else {
            let errorMsg = result.error || "Wake-word listening failed.";
            if (listenRes.status === 403)
              errorMsg = "🔒 Voice did not match the enrolled profile.";
            setMessages((prev) => [...prev, { sender: "ai", text: errorMsg }]);
          }

          // 🕒 wait a few seconds, then unlock polling
          setTimeout(() => {
            wakeLockedRef.current = false;
            setListening(false);
            console.log("🟢 Wake session complete — resuming wakeword polling...");
            startWakePolling(); // restart polling loop
          }, 5000);
        }
      } catch (err) {
        console.warn("⚠️ Wakeword polling failed:", err);
      }
    }

    function startWakePolling() {
      if (wakeIntervalRef.current) clearInterval(wakeIntervalRef.current);
      wakeIntervalRef.current = setInterval(checkWakeword, 4000); // every 4s
    }

    startWakePolling(); // start when app loads
    return () => clearInterval(wakeIntervalRef.current);
  }, [voiceSignatureEnabled]);

  // === 🎙️ Manual listening button ===
  const handleStartListening = async () => {
    setListening(true);
    try {
      const res = await fetch("http://127.0.0.1:5000/listen-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verify_voice: voiceSignatureEnabled }),
      });
      const data = await res.json();

      if (!res.ok) {
        let errorMsg = data.error || "⚠️ Voice recognition failed.";
        if (res.status === 403)
          errorMsg = "🔒 Voice did not match the enrolled profile!";
        else if (data.code === "stt_unknown")
          errorMsg = "😕 I couldn’t understand you. Please speak clearly.";
        else if (data.code === "stt_timeout")
          errorMsg = "⏱️ I didn’t hear anything. Try again.";
        else if (data.code === "stt_api_error")
          errorMsg = "🌐 Speech service unavailable.";

        setMessages((prev) => [...prev, { sender: "ai", text: errorMsg }]);
        setListening(false);
        return;
      }

      setMessages((prev) => [
        ...prev,
        { sender: "user", text: data.text },
        { sender: "ai", text: data.reply },
      ]);

      if (
        data.action === "open_browser" ||
        data.action === "open_app" ||
        data.action === "compose_email"
      ) {
        window.electron?.ipcRenderer?.send("move-window-side");
        setCompactMode(true);
      }
    } catch (err) {
      console.error("🎧 Listening failed:", err);
      setMessages((prev) => [
        ...prev,
        { sender: "ai", text: "⚠️ Backend not responding or mic busy." },
      ]);
    } finally {
      setListening(false);
    }
  };

  return (
    <div
      className={`relative w-full h-full flex items-center justify-center text-white bg-transparent overflow-hidden transition-all duration-1000 ${
        appLoaded ? "opacity-100 scale-100" : "opacity-0 scale-95"
      }`}
    >
      {listening && <MockHaloGlow onIntensityChange={setMicIntensity} />}

      <div
        className={`glass-card relative z-10 flex flex-col transition-all duration-700 ease-in-out ${
          compactMode
            ? "w-full h-full px-5 py-4 rounded-2xl"
            : "w-[900px] h-[580px] p-8 rounded-3xl mx-auto"
        }`}
        style={{
          boxShadow: listening
            ? `
                0 0 ${20 + micIntensity * 60}px rgba(56,189,248,${micIntensity * 1.2}),
                0 0 ${40 + micIntensity * 90}px rgba(232,121,249,${micIntensity * 1.1}),
                0 0 ${80 + micIntensity * 120}px rgba(56,189,248,${micIntensity * 0.9})
              `
            : "none",
          transition: "box-shadow 0.1s linear",
        }}
      >
        <div className="flex flex-col items-center justify-center flex-none space-y-6">
          <h1
            className={`audient-gradient font-extrabold text-7xl tracking-wide select-none ${
              listening ? "animate-pulse" : "animate-float"
            }`}
          >
            Audient
          </h1>

          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4 mt-2">
            <button
              onClick={() => handleStartListening()}
              className={`px-10 py-3 rounded-full text-lg font-medium transition duration-300 shadow-lg backdrop-blur-md ${
                listening
                  ? "bg-cyan-500/80 text-black font-semibold"
                  : "bg-white/10 hover:bg-white/20"
              }`}
            >
              {listening ? "🟢 Listening..." : "🎙️ Start Listening"}
            </button>

            <button
              onClick={() => setVoiceSignatureEnabled(!voiceSignatureEnabled)}
              className={`px-6 py-2 rounded-full text-sm font-medium transition duration-300 shadow-lg backdrop-blur-md ${
                voiceSignatureEnabled
                  ? "bg-cyan-500/80 text-black"
                  : "bg-white/10 hover:bg-white/20"
              }`}
            >
              {voiceSignatureEnabled
                ? "🔒 Voice Signature: ON"
                : "🔓 Voice Signature: OFF"}
            </button>
          </div>
        </div>

        {/* 💬 Chat section */}
        <div
          ref={chatRef}
          className={`conversation flex-1 overflow-y-auto space-y-4 mt-6 transition-all duration-500 ${
            compactMode ? "text-sm px-3 py-2" : "text-base px-6 py-4"
          }`}
        >
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${
                msg.sender === "user" ? "justify-end" : "justify-start"
              } animate-fadeIn`}
            >
              <div
                className={`message-bubble ${
                  msg.sender === "user" ? "user-bubble" : "ai-bubble"
                } ${compactMode ? "max-w-[90%]" : "max-w-[70%]"}`}
              >
                {i === messages.length - 1 && msg.sender === "ai" ? (
                  <Typewriter text={msg.text} speed={25} />
                ) : (
                  msg.text
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ===================================
   🎧 Real-time Halo Glow Visualizer
=================================== */
function MockHaloGlow({ onIntensityChange }) {
  useEffect(() => {
    let audioContext, analyser, source, dataArray, rafId;

    async function initMic() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new AudioContext();
        analyser = audioContext.createAnalyser();
        source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        analyser.fftSize = 512;
        const bufferLength = analyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);

        const update = () => {
          analyser.getByteTimeDomainData(dataArray);
          let sumSquares = 0;
          for (let i = 0; i < bufferLength; i++) {
            const val = (dataArray[i] - 128) / 128;
            sumSquares += val * val;
          }
          const rms = Math.sqrt(sumSquares / bufferLength);
          const intensity = Math.min(rms * 3, 1);
          onIntensityChange(intensity);
          rafId = requestAnimationFrame(update);
        };
        update();
      } catch (err) {
        console.error("🎤 MicHaloGlow error:", err);
      }
    }

    initMic();
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      if (audioContext) audioContext.close();
    };
  }, [onIntensityChange]);
  return null;
}
