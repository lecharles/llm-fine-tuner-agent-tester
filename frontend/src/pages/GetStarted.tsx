import { useState } from "react";
import {
    AlertTriangle, Lightbulb, ShieldCheck,
    Download, CircleCheck,
    Database, Cpu, Box, Columns3,
    ArrowDown,
} from "lucide-react";
import Pager from "../components/Pager";

const SLIDES = 3;

// The Get Started landing: a three-slide carousel. Slide 1 makes the case,
// slide 2 is the one-time local setup, slide 3 is the four-step workflow.
export default function GetStarted() {
    const [slide, setSlide] = useState(0);

    return (
        <div className="page gs">
            {slide === 0 && (
                <div className="gs-slide">
                    <div className="page-eyebrow" style={{ color: "var(--accent-guide)" }}>Why LLM Tuner</div>
                    <h1 className="page-title">Own your AI.</h1>
                    <div className="page-sub">Fine-tune a model on your data, on your machine, that no one can take away.</div>

                    <div className="gs-band gs-danger">
                        <div className="gs-band-head"><AlertTriangle size={15} /> The problem</div>
                        <ul className="gs-points">
                            <li>Frontier LLMs are expensive to run.</li>
                            <li>Real customization means fine-tuning: expert-only, and costly.</li>
                            <li>Hosted access can be throttled, geofenced, or revoked overnight.</li>
                        </ul>
                    </div>
                    <div className="gs-connect"><ArrowDown size={15} /></div>
                    <div className="gs-band gs-info">
                        <div className="gs-band-head"><Lightbulb size={15} /> What changed</div>
                        <ul className="gs-points">
                            <li>Apple Silicon can now fine-tune models on-device, through MLX.</li>
                            <li>Small open-source models are good enough to tune and trust.</li>
                        </ul>
                    </div>
                    <div className="gs-connect"><ArrowDown size={15} /></div>
                    <div className="gs-band gs-success">
                        <div className="gs-band-head"><ShieldCheck size={15} /> LLM Tuner</div>
                        <ul className="gs-points">
                            <li>Build data and fine-tune your own model in a few clicks.</li>
                            <li>It runs on your machine. You own it: full sovereignty, no plug to pull.</li>
                        </ul>
                    </div>
                </div>
            )}

            {slide === 1 && (
                <div className="gs-slide">
                    <div className="page-eyebrow" style={{ color: "var(--accent-guide)" }}>Setup</div>
                    <h1 className="page-title">First, set up your machine.</h1>
                    <div className="page-sub">One opt-in installs the on-device training stack. Nothing leaves your Mac.</div>

                    <div className="card gs-setup">
                        <div className="gs-setup-head">
                            <div className="gs-setup-title">
                                <span className="gs-setup-icon"><Download size={17} /></span>
                                <div>
                                    <div className="gs-setup-name">Step 0 &middot; one-time setup</div>
                                    <div className="gs-setup-tag">on-device</div>
                                </div>
                            </div>
                            <span className="badge badge-success">ready</span>
                        </div>
                        <div className="gs-setup-blurb">Opt in, and LLM Tuner installs everything training needs, then runs entirely on your own hardware.</div>
                        <div className="gs-checklist">
                            <div className="gs-check"><CircleCheck size={15} /> Ollama runtime</div>
                            <div className="gs-check"><CircleCheck size={15} /> MLX (Apple Silicon)</div>
                            <div className="gs-check"><CircleCheck size={15} /> Python dependencies</div>
                            <div className="gs-check"><CircleCheck size={15} /> Base model weights</div>
                        </div>
                        <div className="gs-bar"><div className="gs-bar-fill" /></div>
                        <div className="gs-setup-done"><CircleCheck size={14} /> <b>4 of 4 installed</b>, you're ready to train.</div>
                    </div>
                    <div className="gs-teaser">Next: the four-step workflow &rarr;</div>
                </div>
            )}

            {slide === 2 && (
                <div className="gs-slide">
                    <div className="page-eyebrow" style={{ color: "var(--accent-guide)" }}>The workflow</div>
                    <h1 className="page-title">Then, four steps to your model.</h1>
                    <div className="page-sub">What each part does.</div>

                    <div className="gs-step gs-step-datasets">
                        <span className="gs-step-icon"><Database size={18} /></span>
                        <div>
                            <div className="gs-step-head"><span className="gs-step-name">Datasets</span><span className="gs-step-num">Step 1 &middot; start here</span></div>
                            <div className="gs-step-blurb">Create a dataset for your use case, then generate Q&amp;A pairs from a prompt or import a preset.</div>
                        </div>
                    </div>
                    <div className="gs-connect"><ArrowDown size={15} /></div>
                    <div className="gs-step gs-step-train">
                        <span className="gs-step-icon"><Cpu size={18} /></span>
                        <div>
                            <div className="gs-step-head"><span className="gs-step-name">Train</span><span className="gs-step-num">Step 2</span></div>
                            <div className="gs-step-blurb">Fine-tune a small model on that dataset, right on your own machine.</div>
                        </div>
                    </div>
                    <div className="gs-connect"><ArrowDown size={15} /></div>
                    <div className="gs-step gs-step-models">
                        <span className="gs-step-icon"><Box size={18} /></span>
                        <div>
                            <div className="gs-step-head"><span className="gs-step-name">Models</span><span className="gs-step-num">Step 3</span></div>
                            <div className="gs-step-blurb">Your fine-tuned models collect here, each one ready to test.</div>
                        </div>
                    </div>
                    <div className="gs-connect"><ArrowDown size={15} /></div>
                    <div className="gs-step gs-step-compare">
                        <span className="gs-step-icon"><Columns3 size={18} /></span>
                        <div>
                            <div className="gs-step-head"><span className="gs-step-name">Compare</span><span className="gs-step-num">Step 4</span></div>
                            <div className="gs-step-blurb">Chat four models side by side and watch how tuning changed the answers.</div>
                        </div>
                    </div>
                </div>
            )}

            <div className="gs-nav">
                <Pager page={slide} total={SLIDES} onChange={setSlide} />
            </div>
        </div>
    );
}