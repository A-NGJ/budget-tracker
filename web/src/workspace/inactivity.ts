// Locks the workspace after a period without operator input.
//
// Browsers throttle timers in background tabs, so the deadline is checked
// against wall-clock time on a short interval and again whenever the page
// becomes visible, rather than trusting a single long setTimeout.

export const INACTIVITY_LOCK_MS = 15 * 60 * 1000;
const CHECK_INTERVAL_MS = 15 * 1000;
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "focusin"] as const;

export interface InactivityOptions {
  timeoutMs?: number;
  onIdle: () => void;
  target?: Window;
  now?: () => number;
}

/** Start watching for inactivity. Returns a function that stops watching. */
export function watchInactivity({ timeoutMs = INACTIVITY_LOCK_MS, onIdle, target = window, now = Date.now }: InactivityOptions): () => void {
  let lastActivity = now();
  let stopped = false;

  // Returns true when the deadline has passed and the workspace was locked.
  const check = (): boolean => {
    if (stopped) return true;
    if (now() - lastActivity >= timeoutMs) {
      stop();
      onIdle();
      return true;
    }
    return false;
  };
  // Input arriving after the deadline (e.g. a throttled tab whose interval
  // never fired) must lock, not silently extend the session.
  const markActive = () => {
    if (check()) return;
    lastActivity = now();
  };
  const onVisibility = () => {
    if (target.document.visibilityState === "visible") check();
  };

  for (const event of ACTIVITY_EVENTS) target.addEventListener(event, markActive, { passive: true, capture: true });
  target.document.addEventListener("visibilitychange", onVisibility);
  const interval = target.setInterval(check, Math.min(CHECK_INTERVAL_MS, timeoutMs));

  function stop() {
    if (stopped) return;
    stopped = true;
    target.clearInterval(interval);
    for (const event of ACTIVITY_EVENTS) target.removeEventListener(event, markActive, { capture: true });
    target.document.removeEventListener("visibilitychange", onVisibility);
  }
  return stop;
}
