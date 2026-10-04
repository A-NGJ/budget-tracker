// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { INACTIVITY_LOCK_MS, watchInactivity } from "../../src/workspace/inactivity";

describe("inactivity lock", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("locks fifteen minutes after the last activity", () => {
    vi.useFakeTimers();
    const onIdle = vi.fn();
    const stop = watchInactivity({ onIdle });
    vi.advanceTimersByTime(INACTIVITY_LOCK_MS - 20_000);
    expect(onIdle).not.toHaveBeenCalled();
    vi.advanceTimersByTime(20_000);
    expect(onIdle).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(INACTIVITY_LOCK_MS);
    expect(onIdle).toHaveBeenCalledTimes(1);
    stop();
  });

  it("restarts the countdown on operator input", () => {
    vi.useFakeTimers();
    const onIdle = vi.fn();
    const stop = watchInactivity({ onIdle });
    vi.advanceTimersByTime(INACTIVITY_LOCK_MS - 60_000);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    vi.advanceTimersByTime(INACTIVITY_LOCK_MS - 60_000);
    expect(onIdle).not.toHaveBeenCalled();
    vi.advanceTimersByTime(60_000);
    expect(onIdle).toHaveBeenCalledTimes(1);
    stop();
  });

  it("locks on return to a throttled tab whose deadline already passed", () => {
    let now = 0;
    const onIdle = vi.fn();
    const stop = watchInactivity({ onIdle, now: () => now });
    now = INACTIVITY_LOCK_MS + 1;
    document.dispatchEvent(new Event("visibilitychange"));
    expect(onIdle).toHaveBeenCalledTimes(1);
    stop();
  });

  it("stops watching when stopped", () => {
    vi.useFakeTimers();
    const onIdle = vi.fn();
    watchInactivity({ onIdle })();
    vi.advanceTimersByTime(INACTIVITY_LOCK_MS * 2);
    expect(onIdle).not.toHaveBeenCalled();
  });
});
