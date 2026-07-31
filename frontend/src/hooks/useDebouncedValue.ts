import { useEffect, useState } from "react";

/**
 * Returns `value` delayed by `delayMs`, so a fast-changing input (e.g. a search
 * box) drives at most one downstream request per pause. Used by the registry
 * search so keystrokes don't each trigger a backend query.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
