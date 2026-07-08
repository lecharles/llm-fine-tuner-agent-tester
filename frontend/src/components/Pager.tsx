import { ChevronLeft, ChevronRight } from "lucide-react";

type Props = {
    page: number; // 0-indexed current page
    total: number; // total number of pages
    onChange: (page: number) => void;
};

// A small reusable pager: previous / "n of total" / next. Used by both the
// dataset-detail pairs table and the Get Started carousel.
export default function Pager({ page, total, onChange }: Props) {
    return (
        <div className="pager-controls">
            <button className="pager-btn" onClick={() => onChange(Math.max(0, page - 1))} disabled={page === 0} aria-label="Previous">
                <ChevronLeft size={14} />
            </button>
            <span className="pager-page">{page + 1} / {total}</span>
            <button className="pager-btn" onClick={() => onChange(Math.min(total - 1, page + 1))} disabled={page === total - 1} aria-label="Next">
                <ChevronRight size={14} />
            </button>
        </div>
    );
}