import { useState, useEffect, useRef } from "react";
import Typewriter from "./components/Typewriter";

export default function App() {
  const [listening, setListening] = useState(false);
  const [messages, setMessages] = useState([
    { sender: "ai", text: "👋 Hello! I'm Audient — your voice assistant." },
  ]);
  const [turn, setTurn] = useState("user");
  const [appLoaded, setAppLoaded] = useState(false);
  const chatRef = useRef(null);
  const [compactMode, setCompactMode] = useState(false);
  const [voiceSignatureEnabled, setVoiceSignatureEnabled] = useState(false);

  // ✅ Connection check with preload
  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      console.log("✅ Renderer connected to Electron preload bridge");
      window.electron.ipcRenderer.send("ping-test");
      window.electron.ipcRenderer.on("window-position", (position) => {
        setCompactMode(position === "side");
      });
    } else {
      console.error("❌ window.electron is undefined — preload not loaded");
    }

    // ✨ App entry animation
    const timer = setTimeout(() => setAppLoaded(true), 300);
    return () => clearTimeout(timer);
  }, []);

  // 🧭 Auto-scroll conversation
useEffect(() => {
  if (chatRef.current) {
    // Scroll only if user near bottom
    const el = chatRef.current;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 50; // 50px margin

    if (atBottom) {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: "smooth",
      });
    }
  }
}, [messages]);


  // 🪄 Sync with Electron when listening
  useEffect(() => {
    window.electron?.ipcRenderer?.send("set-listening-mode", listening);
  }, [listening]);

    // 🎤 Passive wake-word listener (poll backend every few seconds)
  useEffect(() => {
    let interval;

    async function checkWakeword() {
      try {
        const res = await fetch("http://127.0.0.1:5000/wakeword", { method: "POST" });
        const data = await res.json();

        if (data.wakeword_detected) {
          console.log("👂 Wake-word detected:", data.text);

          // 🌈 Show instant listening glow
          setListening(true);
          setMessages(prev => [
            ...prev,
            { sender: "user", text: `🎤 (${data.text})` },
          ]);

          // 🧠 Trigger actual voice recognition
          const listenRes = await fetch("http://127.0.0.1:5000/listen-voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ trigger: "wake" }),
          });

          const result = await listenRes.json();
          if (listenRes.ok) {
            setMessages(prev => [
              ...prev,
              { sender: "user", text: result.text },
              { sender: "ai", text: result.reply },
            ]);

            // 🪄 Auto-dock if Gemini opened something
            if (
              result.action === "open_browser" ||
              result.action === "open_app" ||
              result.action === "compose_email"
            ) {
              window.electron?.ipcRenderer?.send("move-window-side");
              setCompactMode(true);
            }
          } else {
            setMessages(prev => [
              ...prev,
              { sender: "ai", text: result.error || "Wake-word listening failed." },
            ]);
          }

          setListening(false);
        }
      } catch (err) {
        console.error("⚠️ Wake-word polling failed:", err);
      }
    }

    // 🕒 check every 5 seconds
    interval = setInterval(checkWakeword, 5000);
    return () => clearInterval(interval);
  }, []);


  // 💬 Manual exchange for testing
  const handleExchange = async () => {
    if (turn === "user") {
      const userText = "Hey VocalAI, summarize my latest notes please.";
      setMessages((prev) => [...prev, { sender: "user", text: userText }]);
      setTurn("ai");

      try {
        const res = await fetch("http://127.0.0.1:5000/listen-voice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trigger: "listen" }),
        });
        const data = await res.json();
        setMessages((prev) => [...prev, { sender: "ai", text: data.reply }]);
      } catch (err) {
        console.error("❌ Backend error:", err);
        setMessages((prev) => [
          ...prev,
          { sender: "ai", text: "⚠️ Couldn’t reach the backend." },
        ]);
      }

      setTurn("user");
    }
  };

  // 🎙️ Handle real Start Listening → send to Flask
  // 🎙️ Handle real Start Listening → send to Flask
  const handleStartListening = async () => {
  const newState = !listening;
  setListening(newState);

  if (newState) {
    try {
      const res = await fetch("http://127.0.0.1:5000/listen-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verify_voice: voiceSignatureEnabled })
      });

        const data = await res.json();

      // Handle error cases
      if (!res.ok) {
        let errorMsg = data.error || "⚠️ Voice recognition failed.";

        if (res.status === 403)
          errorMsg = "🔒 Voice did not match the enrolled profile!";
        else if (data.code === "stt_unknown")
          errorMsg = "😕 I couldn't understand you. Please speak clearly.";
        else if (data.code === "stt_timeout")
          errorMsg = "⏱️ I didn't hear anything. Try speaking again.";
        else if (data.code === "stt_api_error")
          errorMsg = "🌐 Speech service unavailable — check your network.";

        // You can trigger an animation here before showing the message!
        setMessages((prev) => [...prev, { sender: "ai", text: errorMsg }]);
        setListening(false);
        return;
      }

      setMessages((prev) => [
        ...prev,
        { sender: "user", text: data.text },
        { sender: "ai", text: data.reply },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "ai", text: "⚠️ I couldn't hear anything or the backend failed." },
      ]);
    } finally {
      setListening(false);
    }
  }
};

  // 🪟 Move window
  const handleMoveSide = () => {
    window.electron?.ipcRenderer?.send("move-window-side");
    setCompactMode(true);
  };

  const handleMoveCenter = () => {
    window.electron?.ipcRenderer?.send("move-window-center");
    setCompactMode(false);
  };

  return (
    <div
      className={`relative w-full h-full flex items-center justify-center text-white bg-transparent overflow-hidden transition-all duration-1000 ${
        appLoaded ? "opacity-100 scale-100" : "opacity-0 scale-95"
      }`}
    >
      {/* 🎧 Mic-driven glow visualizer */}
      {listening && <MockHaloGlow onIntensityChange={setMicIntensity} />}

      {/* 🪞 Glass Container with mic glow intensity */}
      <div
        className={`glass-card z-10 flex flex-col justify-between transition-all duration-700 ease-in-out
          ${
            compactMode
              ? "w-full h-full px-5 py-4 rounded-2xl"
              : "w-[900px] h-[580px] p-8 rounded-3xl mx-auto"
          }
          ${listening ? "animate-borderGlow" : ""}
        `}
      >
        {/* Header */}
        <div className="flex justify-between items-center mb-3">
          <h1
            className={`font-bold bg-gradient-to-r from-cyan-400 to-fuchsia-500 bg-clip-text text-transparent
              ${compactMode ? "text-2xl" : "text-4xl"}
            `}
          >
            VocalAI
          </h1>
          <button
            onClick={() =>
              compactMode ? handleMoveCenter() : handleStartListening()
            }
            className="bg-white/10 hover:bg-white/20 px-4 py-2 rounded-full text-sm transition"
          >
            {compactMode
              ? "Exit"
              : listening
              ? "Stop Listening"
              : "Start Listening"}
          </button>
          <button
            onClick={() => setVoiceSignatureEnabled(!voiceSignatureEnabled)}
            className="bg-white/10 hover:bg-white/20 px-4 py-2 rounded-full text-sm transition"
          >
            {voiceSignatureEnabled
              ? "🔒 Voice Signature: ON"
              : "🔓 Voice Signature: OFF"}
          </button>
        </div>

        {/* 💬 Conversation scrollable area */}
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
                msg.sender === "user" ? "justify-start" : "justify-end"
              }`}
            >
              <div
                className={`message-bubble ${
                  msg.sender === "user" ? "user-bubble" : "ai-bubble"
                } ${compactMode ? "max-w-[90%]" : "max-w-[70%]"}`}
              >
                {/* ✅ Animate AI or user messages */}
                {i === messages.length - 1 && msg.sender === "ai" ? (
                  <Typewriter text={msg.text} speed={25} />
                ) : (
                  msg.text
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        {listening && (
          <div
            className={`pt-3 border-t border-white/10 w-full flex items-center flex-none ${
              compactMode ? "justify-center gap-3" : "justify-between"
            }`}
          >
            {/* <button
              onClick={handleExchange}
              className="bg-gradient-to-r from-cyan-400 to-fuchsia-500 text-black font-semibold px-5 py-2 rounded-full hover:opacity-90 transition"
            >
              Exchange
            </button> */}

            {/* {!compactMode && (
              <button
                onClick={handleMoveSide}
                className="bg-white/10 hover:bg-white/20 px-4 py-2 rounded-full text-sm transition"
              >
                🪟 Move to Side
              </button>
            )} */}
          </div>
        )}
      </div>
    </div>
  );
}

/* ===================================
   🎧 Real-time Halo Glow Visualizer
=================================== */
function MockHaloGlow({ onIntensityChange }) {
  const [intensity, setIntensity] = useState(0.5);
  const analyserRef = useRef(null);
  const dataArrayRef = useRef(null);
  const animationRef = useRef(null);

  useEffect(() => {
    const interval = setInterval(
      () => setIntensity(0.3 + Math.random() * 0.7),
      400
    );
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="absolute inset-0 z-0 pointer-events-none">
      <div
        className="absolute inset-0 animate-haloEdge rounded-[40px]"
        style={{
          border: `3px solid transparent`,
          borderImage: `linear-gradient(130deg, rgba(56,189,248,${intensity}), rgba(232,121,249,${
            intensity * 0.9
          }), rgba(56,189,248,${intensity})) 1`,
          boxShadow: `
            0 0 ${40 + intensity * 90}px rgba(56,189,248,${intensity * 0.6}),
            0 0 ${60 + intensity * 120}px rgba(232,121,249,${intensity * 0.6})
          `,
          filter: "blur(15px)",
          mixBlendMode: "screen",
        }}
      ></div>
      <div
        className="absolute inset-0 animate-haloPulse"
        style={{
          background: `radial-gradient(circle at center, rgba(56,189,248,${
            intensity * 0.1
          }), rgba(232,121,249,${intensity * 0.05}), transparent 80%)`,
          filter: "blur(120px)",
          opacity: 0.7,
        }}
      ></div>
    </div>
  );
}
