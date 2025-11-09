import { useState, useEffect, useRef } from "react";

export default function App() {
  const [listening, setListening] = useState(false);
  const [messages, setMessages] = useState([
    { sender: "ai", text: "👋 Hello! I'm Audient — your voice assistant." },
  ]);
  const [turn, setTurn] = useState("user");
  const [appLoaded, setAppLoaded] = useState(false);
  const chatRef = useRef(null);
  const [compactMode, setCompactMode] = useState(false);

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
      chatRef.current.scrollTo({
        top: chatRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  // 🪄 Sync with Electron when listening
  useEffect(() => {
    window.electron?.ipcRenderer?.send("set-listening-mode", listening);
  }, [listening]);

  // 💬 Manual exchange for testing
  const handleExchange = async () => {
    if (turn === "user") {
      const userText = "Hey Audient, summarize my latest notes please.";
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
      } catch {
        setMessages((prev) => [
          ...prev,
          { sender: "ai", text: "⚠️ Couldn’t reach the backend." },
        ]);
      }

      setTurn("user");
    }
  };

  // 🎙️ Real listening
  const handleStartListening = async () => {
    const newState = !listening;
    setListening(newState);

    if (newState) {
      try {
        const res = await fetch("http://127.0.0.1:5000/listen-voice", {
          method: "POST",
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || "Voice recognition failed.");

        setMessages((prev) => [
          ...prev,
          { sender: "user", text: data.text },
          { sender: "ai", text: data.reply },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            sender: "ai",
            text: "⚠️ I couldn’t hear anything or the backend failed.",
          },
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
      {/* 🎧 Halo Visualizer */}
      {listening && <MockHaloVisualizer />}

      {/* 🪞 Glass Container */}
      <div
        className={`glass-card relative z-10 flex flex-col transition-all duration-700 ease-in-out ${
          compactMode
            ? "w-full h-full px-5 py-4 rounded-2xl"
            : "w-[900px] h-[580px] p-8 rounded-3xl mx-auto"
        } ${listening ? "animate-borderGlow" : ""}`}
      >
        {/* Header section */}
        <div className="flex flex-col items-center justify-center flex-none space-y-5">
          <h1 className="audient-gradient font-extrabold text-7xl tracking-wide select-none animate-float">
            Audient
          </h1>
          <button
            onClick={() =>
              compactMode ? handleMoveCenter() : handleStartListening()
            }
            className="bg-white/10 hover:bg-white/20 px-10 py-3 rounded-full text-lg font-medium transition duration-300 shadow-lg backdrop-blur-md animate-pulseGlow"
          >
            {compactMode
              ? "Exit"
              : listening
              ? "Stop Listening"
              : "Start Listening"}
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
                msg.sender === "user" ? "justify-end" : "justify-start"
              } animate-fadeIn`}
            >
              <div
                className={`message-bubble ${
                  msg.sender === "user" ? "user-bubble" : "ai-bubble"
                } ${compactMode ? "max-w-[90%]" : "max-w-[70%]"}`}
              >
                {msg.text}
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
            <button
              onClick={handleExchange}
              className="bg-gradient-to-r from-cyan-400 to-fuchsia-500 text-black font-semibold px-5 py-2 rounded-full hover:opacity-90 transition"
            >
              Exchange
            </button>

            {!compactMode && (
              <button
                onClick={handleMoveSide}
                className="bg-white/10 hover:bg-white/20 px-4 py-2 rounded-full text-sm transition"
              >
                🪟 Move to Side
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ===================================
   🎧 Halo Visualizer (glow animation)
=================================== */
function MockHaloVisualizer() {
  const [intensity, setIntensity] = useState(0.5);
  const analyserRef = useRef(null);
  const dataArrayRef = useRef(null);
  const animationRef = useRef(null);

  useEffect(() => {
    let audioContext;
    let source;

    async function setupMic() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        source = audioContext.createMediaStreamSource(stream);

        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        analyserRef.current = analyser;
        dataArrayRef.current = dataArray;
        source.connect(analyser);

        const animate = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteTimeDomainData(dataArrayRef.current);

          let sum = 0;
          for (let i = 0; i < dataArrayRef.current.length; i++) {
            const val = dataArrayRef.current[i] - 128;
            sum += val * val;
          }
          const rms = Math.sqrt(sum / dataArrayRef.current.length);
          const newIntensity = Math.min(1, rms / 30);
          setIntensity(newIntensity);

          animationRef.current = requestAnimationFrame(animate);
        };
        animate();
      } catch (err) {
        console.error("🎤 Mic setup failed:", err);
      }
    }

    setupMic();
    return () => {
      cancelAnimationFrame(animationRef.current);
      if (audioContext) audioContext.close();
    };
  }, []);

  return (
    <div className="absolute inset-0 z-0 pointer-events-none">
      <div
        className="absolute inset-0 rounded-[40px]"
        style={{
          border: `2px solid transparent`,
          borderImage: `linear-gradient(130deg, rgba(56,189,248,${intensity}), rgba(232,121,249,${intensity * 0.9}), rgba(56,189,248,${intensity})) 1`,
          boxShadow: `
            0 0 ${6 + intensity * 12}px rgba(56,189,248,${intensity * 0.5}),
            0 0 ${10 + intensity * 18}px rgba(232,121,249,${intensity * 0.5})
          `,
          filter: "blur(8px)",
          mixBlendMode: "screen",
          transition: "box-shadow 0.15s linear",
        }}
      ></div>
    </div>
  );
}
