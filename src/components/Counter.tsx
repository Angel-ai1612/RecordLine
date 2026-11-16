import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

/** Counts from 0 to a fraction and renders it as a percentage. */
export function Counter({ value, className }: { value: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduce) {
      el.textContent = `${Math.round(value * 100)}%`;
      return;
    }
    const c = animate(0, value, {
      duration: 0.9,
      ease: [0.2, 0.7, 0.2, 1],
      onUpdate: (v) => (el.textContent = `${Math.round(v * 100)}%`),
    });
    return () => c.stop();
  }, [value, reduce]);
  return <span ref={ref} className={className}>0%</span>;
}
