/** The app's persisted client state, in one place with one shape.
 *
 * This was four ad-hoc AsyncStorage calls inside session.tsx. It is a registry now
 * because the set is growing (a session to resume, a rail preference) and because
 * every one of them has the same requirement: storage failing is never a reason for
 * the app not to start. A private window, a cleared device, a platform that has no
 * storage at all - each reads as a fresh install rather than an error.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

export const KEYS = {
  authed: "umbra-authed",
  onboarded: "umbra-onboarded",
  server: "umbra-server",
  token: "umbra-token",
  /** The session to resume on next launch. */
  thread: "umbra-thread",
  /** "expanded" | "collapsed". Absent means "decide from the window width". */
  rail: "umbra-rail",
} as const;

export type StorageKey = (typeof KEYS)[keyof typeof KEYS];

/** One round trip for everything the app needs at launch. */
export async function readMany<K extends StorageKey>(keys: K[]): Promise<Record<K, string | null>> {
  const out = {} as Record<K, string | null>;
  for (const key of keys) out[key] = null;
  try {
    for (const [key, value] of await AsyncStorage.multiGet(keys)) {
      out[key as K] = value;
    }
  } catch {
    // Treated as a fresh install; the defaults above already stand.
  }
  return out;
}

/** Writing null removes the key, so callers never have to pick between two calls. */
export async function write(key: StorageKey, value: string | null): Promise<void> {
  try {
    if (value === null) await AsyncStorage.removeItem(key);
    else await AsyncStorage.setItem(key, value);
  } catch {
    // A preference that did not persist is not worth failing a user action over.
  }
}

export async function remove(keys: StorageKey[]): Promise<void> {
  try {
    await AsyncStorage.multiRemove(keys);
  } catch {
    // As above.
  }
}
