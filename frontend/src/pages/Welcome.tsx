import { Link } from "react-router-dom";
import {
    Sparkles, Database, Cpu, Columns3,
    ShieldCheck, ArrowRight, ArrowDown, Play,
} from "lucide-react";

// The Welcome / motivation landing (S4): a single-scroll page that makes the
// case for local fine-tuning and funnels into the loop. Distinct from the
// Get Started carousel (setup + workflow reference) — this is the emotional
// front door and the `llmtuner app` landing target (D2).
// S19 (a11y): CTAs are real router Links (middle-click/open-in-new-tab work,
// and screen readers announce them as links); decorative icons are aria-hidden.
export default function Welcome() {
    return (
        <div className="page gs">
            <div className="gs-slide">
                <div className="page-eyebrow" style={{ color: "var(--accent-guide)" }}>
                    <Sparkles size={13} aria-hidden="true" style={{ verticalAlign: "-2px" }} /> Welcome
                </div>
                <h1 className="page-title">Teach a model<br />your world.</h1>
                <div className="page-sub">
                    LLM Tuner turns your knowledge into a fine-tuned model that runs
                    on your machine — no cloud bill, no revoked access, no one else's rules.
                </div>

                <div className="gs-cta-row">
                    <Link to="/datasets" className="btn btn-primary">
                        <Play size={15} aria-hidden="true" /> Start tuning <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                    <Link to="/get-started" className="btn btn-ghost">
                        How it works
                    </Link>
                </div>

                <div className="gs-step gs-step-datasets">
                    <span className="gs-step-icon" aria-hidden="true"><Database size={18} /></span>
                    <div>
                        <div className="gs-step-head"><span className="gs-step-name">1 · Bring knowledge</span><span className="gs-step-num">minutes</span></div>
                        <div className="gs-step-blurb">Describe your use case once — LLM Tuner generates Q&amp;A pairs into a dataset you can edit.</div>
                    </div>
                </div>
                <div className="gs-connect"><ArrowDown size={15} aria-hidden="true" /></div>
                <div className="gs-step gs-step-train">
                    <span className="gs-step-icon" aria-hidden="true"><Cpu size={18} /></span>
                    <div>
                        <div className="gs-step-head"><span className="gs-step-name">2 · Train locally</span><span className="gs-step-num">Apple Silicon</span></div>
                        <div className="gs-step-blurb">QLoRA fine-tuning through MLX, on your Mac. Watch live loss; failures surface loudly, never silently.</div>
                    </div>
                </div>
                <div className="gs-connect"><ArrowDown size={15} aria-hidden="true" /></div>
                <div className="gs-step gs-step-compare">
                    <span className="gs-step-icon" aria-hidden="true"><Columns3 size={18} /></span>
                    <div>
                        <div className="gs-step-head"><span className="gs-step-name">3 · Prove it</span><span className="gs-step-num">side by side</span></div>
                        <div className="gs-step-blurb">Chat base vs tuned models in four columns and see the difference your data made.</div>
                    </div>
                </div>

                <div className="gs-band gs-success">
                    <div className="gs-band-head"><ShieldCheck size={15} aria-hidden="true" /> Yours, even offline</div>
                    <ul className="gs-points">
                        <li>Local Ollama engines answer when cloud credits run dry.</li>
                        <li>Weights live on your disk — nothing to throttle or take away.</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}
