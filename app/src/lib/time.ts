/** Job timestamps, written the way the design speaks: lowercase, short, and
 * relative while that is still the useful thing to say. */

const MIN = 60_000;
const HOUR = 60 * MIN;

/** "just now", "4 min ago", "2 hr ago" - for work that is still in flight. */
export function relative(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const delta = Date.now() - then;
  if (delta < MIN) return "just now";
  if (delta < HOUR) {
    const m = Math.round(delta / MIN);
    return `${m} min ago`;
  }
  const h = Math.round(delta / HOUR);
  if (h < 24) return `${h} hr ago`;
  return calendar(iso);
}

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

/** "today 10:42", "yesterday", "aug 30" - for work that has settled. */
export function calendar(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const days = Math.floor((startOfToday.getTime() - new Date(d).setHours(0, 0, 0, 0)) / 86_400_000);

  if (days <= 0) {
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `today ${hh}:${mm}`;
  }
  if (days === 1) return "yesterday";
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}
