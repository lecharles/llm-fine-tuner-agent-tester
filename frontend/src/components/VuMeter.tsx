type Props = {
    bars?: number; // how many meter bars to draw (default 5)
    className?: string; // optional placement class from the caller
};

// S18 theme pass 2: the one loading idiom for the whole app — short VU-meter
// bars that bounce in the current accent color, so page loads and the compare
// columns all say "working…" the same way. Purely decorative: it inherits
// `currentColor` for theming and is aria-hidden, the label next to it (or a
// visible status line) carries the meaning for screen readers.
export default function VuMeter({ bars = 5, className }: Props) {
    return (
        <span className={`vu-meter${className ? ` ${className}` : ""}`} aria-hidden="true">
            {Array.from({ length: bars }, (_, i) => (
                <span className="vu-bar" key={i} style={{ animationDelay: `${(i % 5) * 0.12}s` }} />
            ))}
        </span>
    );
}
