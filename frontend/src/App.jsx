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
  const [micIntensity, setMicIntensity] = useState(0); // 🔊 RMS-driven glow strength
  
  // ✅ 1. Added voice signature state
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
            // ✅ 4. Updated wake-word call
            body: JSON.stringify({
              trigger: "wake",
              verify_voice: voiceSignatureEnabled 
            }),
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
            // ✅ 4. Added 403 check to wake-word
            let errorMsg = result.error || "Wake-word listening failed.";
            if (listenRes.status === 403) {
              errorMsg = "🔒 Wake-word ignored. Voice did not match profile.";
            }
            setMessages(prev => [
              ...prev,
              { sender: "ai", text: errorMsg },
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
  // ✅ 4. Added voiceSignatureEnabled as a dependency
  }, [voiceSignatureEnabled]); 


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
          // ✅ 5. Updated handleExchange call
          body: JSON.stringify({ 
            trigger: "listen",
            verify_voice: voiceSignatureEnabled
          }),
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

  // 🎙️ Handle real Start Listening → send to Flask
  // ✅ 3. REPLACED this function with the logic from the example
  const handleStartListening = async () => {
    // Don't toggle here, just set to true
    setListening(true);
  
    try {
      const res = await fetch("http://127.0.0.1:5000/listen-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verify_voice: voiceSignatureEnabled })
      });
  
      const data = await res.json();
  
      // Handle error cases
      if (!res.ok) {
        console.warn("🎧 STT error:", data);
        let errorMsg = data.error || "⚠️ Voice recognition failed.";
  
        // ✅ 3. Added 403 error check
        if (res.status === 403)
          errorMsg = "🔒 Voice did not match the enrolled profile!";
        else if (data.code === "stt_unknown")
          errorMsg = "😕 I couldn’t understand you. Please speak clearly.";
        else if (data.code === "stt_timeout")
          errorMsg = "⏱️ I didn’t hear anything. Try speaking again.";
        else if (data.code === "stt_api_error")
          errorMsg = "🌐 Speech service unavailable — check your network.";
  
        setMessages((prev) => [...prev, { sender: "ai", text: errorMsg }]);
        setListening(false);
        return;
      }
  
      // ✅ 3. This now handles the single response (text and reply)
      setMessages((prev) => [
        ...prev,
        { sender: "user", text: data.text },
        { sender: "ai", text: data.reply },
      ]);

      // 🪄 Auto-dock if Gemini opened something
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
        { sender: "ai", text: "⚠️ I couldn’t hear anything or the backend failed." },
      ]);
    } finally {
      setListening(false);
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
        {/* Header section */}
        <div className="flex flex-col items-center justify-center flex-none space-y-5">
          <h1 className="audient-gradient font-extrabold text-7xl tracking-wide select-none animate-float">
            Audient
          </h1>
          <button
            onClick={() =>
              compactMode ? handleMoveCenter() : handleStartListening()
            }
            className={`px-10 py-3 rounded-full text-lg font-medium transition duration-300 shadow-lg backdrop-blur-md ${
              listening
                ? "bg-cyan-500/80 text-black font-semibold"
                : "bg-white/10 hover:bg-white/20"
            }`}
          >
            {compactMode
              ? "Exit"
              : listening
              ? "🟢 Listening..."
              : "🎙️ Start Listening"}
          </button>

          {/* ✅ 2. Added Toggle Button */}
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
            {/* ... (footer content commented out, as in your original) ... */}
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
          onIntensityChange(newIntensity); // 🔥 Pass intensity to parent glow
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
  }, [onIntensityChange]);

  return null; // No visible overlay needed — controls .glass-card glow
}