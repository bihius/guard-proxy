/**
 * The backend serializes naive UTC timestamps (no `Z`/offset suffix), which
 * `new Date()` would otherwise interpret as local time. Treat a timestamp
 * without a timezone designator as UTC.
 */
export function parseUtc(iso: string): Date {
  const hasTimezone = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTimezone ? iso : `${iso}Z`);
}

/** Local date and time of a backend timestamp, or "—" when it is unparseable. */
export function formatDateTime(
  iso: string,
  options: Intl.DateTimeFormatOptions = { dateStyle: "short", timeStyle: "medium" },
): string {
  const date = parseUtc(iso);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(undefined, options).format(date);
}
