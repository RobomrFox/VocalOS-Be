import { useState, useEffect, useRef } from "react";

export default function App() {
  const [listening, setListening] = useState(false);
  const [messages, setMessages] = useState([
    { sender: "ai", text: "👋 Hello! I'm VocalAI — your voice assistant mockup." },
  ]);
  const [turn, setTurn] = useState("user");
  const chatRef = useRef(null);
  const [compactMode, setCompactMode] = useState(false);

  // ✅ Connection check with preload
  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      console.log("✅ Renderer connected to Electron preload bridge");
      window.electron.ipcRenderer.send("ping-test");

      // Listen to messages from main process
      window.electron.ipcRenderer.on("window-position", (position) => {
        setCompactMode(position === "side");
      });
    } else {
      console.error("❌ window.electron is undefined — preload not loaded");
    }
  }, []);

  // 💬 Mock exchange between user ↔ AI
  const handleMockExchange = () => {
    if (turn === "user") {
      setMessages((prev) => [
        ...prev,
        { sender: "user", text: "Hey VocalAI, summarize my latest notes please." },
      ]);
      setTurn("ai");

      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            sender: "ai",
            text: "Sure! You wanted to finish your cabinet plan and adjust lighting next week. I’ve noted it.",
          },
        ]);
        setTurn("user");
      }, 1200);
    }
  };

  // 🧭 Auto-scroll conversation
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTo({
        top: chatRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  // 🪄 Send resize signal to Electron when listening toggles
  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      window.electron.ipcRenderer.send("set-listening-mode", listening);
      console.log(`🎧 Sent listening mode → ${listening}`);
    }
  }, [listening]);

  

  // 🪟 Move to Siri-style side layout
  const handleMoveSide = () => {
    if (window.electron?.ipcRenderer) {
      console.log("🪟 Docking VocalAI to right side...");
      window.electron.ipcRenderer.send("move-window-side");
      setCompactMode(true);
    } else {
      console.error("❌ IPC bridge not available — preload not loaded");
    }
  };

  // 🏠 Return to center layout
  const handleMoveCenter = () => {
    if (window.electron?.ipcRenderer) {
      console.log("🪟 Returning VocalAI to center...");
      window.electron.ipcRenderer.send("move-window-center");
      setCompactMode(false);
    }
  };

return (
  <div className="relative w-full h-full flex items-center justify-center text-white bg-transparent overflow-hidden">
    {/* Halo Visualizer */}
    {listening && <MockHaloVisualizer />}

    {/* Glass Container */}
    <div
      className={`glass-card z-10 flex flex-col justify-between transition-all duration-700 ease-in-out
        ${compactMode ? "w-full h-full px-5 py-4 rounded-2xl" : "w-[900px] h-[580px] p-8 rounded-3xl mx-auto"}
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
          onClick={() => (compactMode ? handleMoveCenter() : setListening(!listening))}
          className="bg-white/10 hover:bg-white/20 px-4 py-2 rounded-full text-sm transition"
        >
          {compactMode ? "Exit" : listening ? "Stop Listening" : "Start Listening"}
        </button>
      </div>

      {/* Conversation */}
      <div
        ref={chatRef}
        className={`conversation flex-1 w-full overflow-y-auto space-y-4 transition-all duration-500
          ${compactMode ? "text-sm px-2 py-2" : "text-base px-4 py-4"}
        `}
      >
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.sender === "user" ? "justify-start" : "justify-end"}`}
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
          className={`mt-3 flex items-center border-t border-white/10 pt-3 ${
            compactMode ? "justify-center gap-2" : "justify-between"
          }`}
        >
          <button
            onClick={handleMockExchange}
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

// 🌌 Halo Visualizer Effect
function MockHaloVisualizer() {
  const [intensity, setIntensity] = useState(0.5);

  useEffect(() => {
    const interval = setInterval(() => setIntensity(0.3 + Math.random() * 0.7), 400);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="absolute inset-0 z-0 pointer-events-none">
      <div
        className="absolute inset-0 animate-haloEdge rounded-[40px]"
        style={{
          border: `3px solid transparent`,
          borderImage: `linear-gradient(130deg, rgba(56,189,248,${intensity}), rgba(232,121,249,${intensity * 0.9}), rgba(56,189,248,${intensity})) 1`,
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
          background: `radial-gradient(circle at center, rgba(56,189,248,${intensity * 0.1}), rgba(232,121,249,${intensity * 0.05}), transparent 80%)`,
          filter: "blur(120px)",
          opacity: 0.7,
        }}
      ></div>
    </div>
  );
}
