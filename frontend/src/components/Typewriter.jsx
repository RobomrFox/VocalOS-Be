import { useEffect, useState, useRef } from "react";

/**
 * Stable Typewriter for chat messages.
 * Prevents skipped first letter and ensures smooth typing.
 */
export default function Typewriter({ text = "", speed = 10, active = true }) {
  const [displayedText, setDisplayedText] = useState("");
  const indexRef = useRef(0);
  const typingRef = useRef(null);

  useEffect(() => {
    // 🧹 Clear any previous timers
    clearTimeout(typingRef.current);

    // 🪄 Reset state for new text
    indexRef.current = 0;
    setDisplayedText("");

    if (!active || !text) {
      setDisplayedText(text);
      return;
    }

    // ✅ Delay start slightly to ensure first render completes
    const startTyping = () => {
      const typeNext = () => {
        const nextChar = text.charAt(indexRef.current);
        setDisplayedText((prev) => prev + nextChar);
        indexRef.current += 1;

        if (indexRef.current < text.length) {
          typingRef.current = setTimeout(typeNext, speed);
        }
      };

      // Start typing loop
      typeNext();
    };

    // Small delay ensures React applies the reset before typing starts
    typingRef.current = setTimeout(startTyping, 20);

    return () => clearTimeout(typingRef.current);
  }, [text, active, speed]);

  return <span>{displayedText}</span>;
}