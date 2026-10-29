import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

type Tint = "info" | "success" | "primary";

type Props = {
    icon: LucideIcon;
    tint?: Tint;
    title: string;
    hint: ReactNode;
    action?: ReactNode;
};

// S39: one brand treatment for every empty list in the app — an accent-tinted
// icon chip (same visual family as the model cards' `.model-icon`), a plain
// title, a one-line hint that points at the way out, and an optional CTA.
// Token-driven, so light and dark both stay AA-legible without per-theme rules.
export default function EmptyState({ icon: Icon, tint = "info", title, hint, action }: Props) {
    return (
        <div className={`empty-state es-${tint}`}>
            <span className="empty-state-icon" aria-hidden="true">
                <Icon size={16} />
            </span>
            <div className="empty-state-body">
                <p className="empty-state-title">{title}</p>
                <p className="empty-state-hint">{hint}</p>
                {action && <div className="empty-state-action">{action}</div>}
            </div>
        </div>
    );
}
