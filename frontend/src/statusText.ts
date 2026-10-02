// S17 (theme pass 1): one shared cleaner label for raw backend status strings.
// Backend statuses arrive snake/kebab-cased and lowercase ("running",
// "fine_tuned"); the UI shows them sentence-cased with plain spaces so badges
// read like words, not enum keys. Colors stay per-page (they encode meaning
// differently for runs vs. models vs. dataset sources).
export function displayStatus(raw: string): string {
    const spaced = raw.replace(/[_-]+/g, " ").trim();
    if (!spaced) return raw;
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
