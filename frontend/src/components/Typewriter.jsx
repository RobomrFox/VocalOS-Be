import { useEffect, useState } from "react";

/**
 * Simulates a typing animation for text.
 * 
 * @param {string} text - The full text to display.
 * @param {number} speed - Milliseconds per character.
 * @param {boolean} active - Whether typing is active.
 */
export default function Typewriter({ text = "", speed = 25, active = true }) {
  const [displayedText, setDisplayedText] = useState("");

  useEffect(() => {
    if (!active || !text) return setDisplayedText(text);

    let i = 0;
    const interval = setInterval(() => {
      setDisplayedText((prev) => prev + text.charAt(i));
      i++;
      if (i >= text.length) clearInterval(interval);
    }, speed);

    return () => clearInterval(interval);
  }, [text, active, speed]);

  return <span>{displayedText}</span>;
}
