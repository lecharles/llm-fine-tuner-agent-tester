import type { LossPoint } from "../types";

// S11 (issue #4): tiny loss curve for the Train page. Deliberately
// dependency-free — an inline SVG polyline scaled to the observed ranges.
// The parent re-renders it on every poll tick, so the line grows live while
// the run is going; once terminal the last fetch is the finished curve.
type Props = {
    points: LossPoint[];
    iters?: number; // planned total iterations, used only to stretch the x-axis
};

const W = 520;
const H = 150;
const PAD_L = 44;
const PAD_R = 10;
const PAD_T = 12;
const PAD_B = 22;

export default function LossChart({ points, iters }: Props) {
    if (points.length === 0) {
        return (
            <div className="loss-empty">
                No loss points yet — the curve appears once the trainer logs its first iteration.
            </div>
        );
    }

    const xs = points.map((p) => p.step);
    const ys = points.map((p) => p.loss);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs, iters ?? 0);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = maxX - minX || 1; // a single point still renders (dot)
    const spanY = maxY - minY || 1;

    const sx = (x: number) => PAD_L + ((x - minX) / spanX) * (W - PAD_L - PAD_R);
    const sy = (y: number) => PAD_T + (1 - (y - minY) / spanY) * (H - PAD_T - PAD_B);

    const polyline = points.map((p) => `${sx(p.step).toFixed(1)},${sy(p.loss).toFixed(1)}`).join(" ");
    const last = points[points.length - 1];

    return (
        <figure className="loss-chart">
            <svg
                viewBox={`0 0 ${W} ${H}`}
                role="img"
                aria-label={`Training loss, ${points.length} points, latest iter ${last.step} at loss ${last.loss.toFixed(4)}`}
            >
                {/* axes */}
                <line x1={PAD_L} y1={H - PAD_B} x2={W - PAD_R} y2={H - PAD_B} className="loss-axis" />
                <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={H - PAD_B} className="loss-axis" />
                {/* y range labels: top + bottom of the observed window */}
                <text x={PAD_L - 6} y={PAD_T + 4} textAnchor="end" className="loss-tick">{maxY.toFixed(2)}</text>
                <text x={PAD_L - 6} y={H - PAD_B} textAnchor="end" className="loss-tick">{minY.toFixed(2)}</text>
                {/* the curve (and a dot when there is only one point) */}
                {points.length > 1 && <polyline points={polyline} className="loss-line" />}
                <circle cx={sx(last.step)} cy={sy(last.loss)} r={3} className="loss-dot" />
                {/* latest values */}
                <text x={W - PAD_R} y={PAD_T + 4} textAnchor="end" className="loss-current">
                    iter {last.step} · loss {last.loss.toFixed(3)}
                </text>
                <text x={W - PAD_R} y={H - 6} textAnchor="end" className="loss-tick">
                    {maxX} iters
                </text>
            </svg>
        </figure>
    );
}
