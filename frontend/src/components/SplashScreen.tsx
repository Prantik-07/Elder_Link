import { motion } from "framer-motion";
import { useReducedMotion } from "../lib/useReducedMotion";

const WRITE_SECONDS = 2.6;
const LOAD_SECONDS = 3.2;

// Pen path: a tight up-and-down sweep from x=30 to x=490, thick enough that
// the strokes overlap and cover every letter it passes over.
const PEN_WIDTH = 34;
const PEN_PATH = Array.from({ length: 22 }, (_, i) => {
  const x = 30 + i * 21;
  const y = i % 2 === 0 ? 8 : 130;
  return `${i === 0 ? "M" : "L"}${x} ${y}`;
}).join(" ");

const TEXT_PROPS = {
  x: 260,
  y: 100,
  textAnchor: "middle" as const,
  fontSize: 112,
  fontWeight: 600,
  style: { fontFamily: "var(--font-hand)" },
};

/**
 * Intro screen: "ElderLink" is handwritten stroke by stroke, like the classic
 * "hello" animation - the pen line draws each letter's outline, then the ink
 * fills in - above a loading bar whose fill is led by the logo mark.
 */
export function SplashScreen() {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[var(--color-ivory)] px-6"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      role="status"
      aria-label="Loading ElderLink"
    >
      <svg viewBox="0 0 520 150" className="h-auto w-full max-w-[34rem]" aria-hidden="true">
        {reduced ? (
          <text {...TEXT_PROPS} fill="var(--color-ink)">
            ElderLink
          </text>
        ) : (
          <>
            <defs>
              {/* One continuous pen path sweeping from the left end to the right end;
                  as it is drawn it uncovers the ink beneath it. */}
              <mask id="splash-pen-mask" maskUnits="userSpaceOnUse" x={0} y={0} width={520} height={150}>
                <motion.path
                  d={PEN_PATH}
                  fill="none"
                  stroke="#fff"
                  strokeWidth={PEN_WIDTH}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: WRITE_SECONDS, ease: "easeInOut" }}
                />
              </mask>
            </defs>
            <text {...TEXT_PROPS} fill="var(--color-ink)" mask="url(#splash-pen-mask)">
              ElderLink
            </text>
          </>
        )}
      </svg>

      <div className="mt-6 w-full max-w-[18rem]">
        {/* Track: the fill grows left to right and the logo mark rides its leading edge. */}
        <div className="relative h-2.5 rounded-full bg-[var(--color-line-soft)]">
          <motion.div
            className="absolute inset-y-0 left-0 rounded-full bg-[var(--color-teal)]"
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{ duration: LOAD_SECONDS, ease: "easeInOut" }}
          />
          <motion.img
            src="/assets/logo-mark.png"
            alt=""
            aria-hidden="true"
            className="absolute top-1/2 h-8 w-auto -translate-y-1/2"
            initial={{ left: "0%", x: "-10%" }}
            animate={{ left: "100%", x: "-90%" }}
            transition={{ duration: LOAD_SECONDS, ease: "easeInOut" }}
          />
        </div>
      </div>
    </motion.div>
  );
}
