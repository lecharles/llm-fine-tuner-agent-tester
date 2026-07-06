import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../api";
import type { Dataset, QAPair } from "../types";

export default function DatasetDetail() {
    const { datasetId } = useParams<{ datasetId: string }>();

    const [dataset, setDataset] = useState<Dataset | null>(null);
    const [pairs, setPairs] = useState<QAPair[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [question, setQuestion] = useState("");
    const [answer, setAnswer] = useState("");
    const [creating, setCreating] = useState(false);

    const [editingId, setEditingId] = useState<number | null>(null);
    const [editQuestion, setEditQuestion] = useState("");
    const [editAnswer, setEditAnswer] = useState("");

    // A2: use-case prompt editor + generate-from-prompt controls.
    const [prompt, setPrompt] = useState("");
    const [savingPrompt, setSavingPrompt] = useState(false);
    const [genCount, setGenCount] = useState(20);
    const [generating, setGenerating] = useState(false);

    // A3: import-from-preset controls.
    const [preset, setPreset] = useState("general");
    const [impCount, setImpCount] = useState(50);
    const [importing, setImporting] = useState(false);

    useEffect(() => {
        Promise.all([
            apiFetch<Dataset>(`/datasets/${datasetId}`),
            apiFetch<QAPair[]>(`/datasets/${datasetId}/qa-pairs`),
        ])
            .then(([d, p]) => {
                setDataset(d);
                setPairs(p);
                setPrompt(d.use_case_prompt ?? "");
            })
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
            .finally(() => setLoading(false));
    }, [datasetId]);

    async function handleCreate(e: React.FormEvent) {
        e.preventDefault();
        setCreating(true);
        setError(null);
        try {
            const created = await apiFetch<QAPair>(`/datasets/${datasetId}/qa-pairs`, {
                method: "POST",
                body: { question, answer },
            });
            setPairs((prev) => [...prev, created]);
            setQuestion("");
            setAnswer("");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Create failed");
        } finally {
            setCreating(false);
        }
    }

    function startEdit(p: QAPair) {
        setEditingId(p.id);
        setEditQuestion(p.question);
        setEditAnswer(p.answer);
        setError(null);
    }

    async function handleSave(id: number) {
        setError(null);
        try {
            const updated = await apiFetch<QAPair>(`/datasets/${datasetId}/qa-pairs/${id}`, {
                method: "PUT",
                body: { question: editQuestion, answer: editAnswer },
            });
            setPairs((prev) => prev.map((p) => (p.id === id ? updated : p)));
            setEditingId(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Update failed");
        }
    }

    async function handleDelete(id: number) {
        setError(null);
        try {
            await apiFetch<null>(`/datasets/${datasetId}/qa-pairs/${id}`, { method: "DELETE" });
            setPairs((prev) => prev.filter((p) => p.id !== id));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
        }
    }

    // A2: save the dataset's use_case_prompt, then generate pairs from it.
    async function handleSavePrompt() {
        setSavingPrompt(true);
        setError(null);
        try {
            const updated = await apiFetch<Dataset>(`/datasets/${datasetId}`, {
                method: "PUT",
                body: { use_case_prompt: prompt },
            });
            setDataset(updated);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Save failed");
        } finally {
            setSavingPrompt(false);
        }
    }

    async function handleGenerate() {
        setGenerating(true);
        setError(null);
        try {
            const created = await apiFetch<QAPair[]>(`/datasets/${datasetId}/generate`, {
                method: "POST",
                body: { count: genCount },
            });
            setPairs((prev) => [...prev, ...created]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Generate failed");
        } finally {
            setGenerating(false);
        }
    }

    async function handleImport() {
        setImporting(true);
        setError(null);
        try {
            const created = await apiFetch<QAPair[]>(`/datasets/${datasetId}/import`, {
                method: "POST",
                body: { preset, count: impCount },
            });
            setPairs((prev) => [...prev, ...created]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Import failed");
        } finally {
            setImporting(false);
        }
    }

    return (
        <div>
            <p><Link to="/datasets">← Datasets</Link></p>

            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}

            {!loading && dataset && (
                <>
                    <h1>{dataset.name}</h1>
                    <p>{dataset.description ?? "no description"} ({dataset.source})</p>
                    <div>
                        <p>Use-case prompt (generation uses this):</p>
                        <textarea
                            placeholder="e.g. A terse assistant that answers in one sentence"
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                        />
                        <button onClick={handleSavePrompt} disabled={savingPrompt}>
                            {savingPrompt ? "Saving..." : "Save prompt"}
                        </button>
                    </div>

                    <h2>QA pairs ({pairs.length})</h2>

                    <form onSubmit={handleCreate}>
                        <input
                            placeholder="Question"
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            required
                        />
                        <input
                            placeholder="Answer"
                            value={answer}
                            onChange={(e) => setAnswer(e.target.value)}
                            required
                        />
                        <button type="submit" disabled={creating}>
                            {creating ? "Adding..." : "Add pair"}
                        </button>
                    </form>

                    <div>
                        <p>Generate pairs from the prompt:</p>
                        <input
                            type="number"
                            min={1}
                            max={100}
                            value={genCount}
                            onChange={(e) => setGenCount(Number(e.target.value))}
                        />
                        <button
                            onClick={handleGenerate}
                            disabled={generating || genCount < 1 || !dataset.use_case_prompt}
                        >
                            {generating ? "Generating..." : "Generate"}
                        </button>
                        {!dataset.use_case_prompt && <span> Save a use-case prompt first.</span>}
                    </div>

                    <div>
                        <p>Import pairs from a preset dataset:</p>
                        <select value={preset} onChange={(e) => setPreset(e.target.value)}>
                            <option value="general">General instructions (Dolly)</option>
                            <option value="finance">Finance Q&A</option>
                        </select>
                        <input
                            type="number"
                            min={1}
                            max={500}
                            value={impCount}
                            onChange={(e) => setImpCount(Number(e.target.value))}
                        />
                        <button onClick={handleImport} disabled={importing || impCount < 1}>
                            {importing ? "Importing..." : "Import"}
                        </button>
                    </div>

                    {pairs.length === 0 && <p>No QA pairs yet.</p>}

                    <ul>
                        {pairs.map((p) => (
                            <li key={p.id}>
                                {editingId === p.id ? (
                                    <>
                                        <input value={editQuestion} onChange={(e) => setEditQuestion(e.target.value)} />
                                        <input value={editAnswer} onChange={(e) => setEditAnswer(e.target.value)} />
                                        <button onClick={() => handleSave(p.id)}>Save</button>
                                        <button onClick={() => setEditingId(null)}>Cancel</button>
                                    </>
                                ) : (
                                    <>
                                        <strong>Q:</strong> {p.question} <strong>A:</strong> {p.answer}{" "}
                                        <button onClick={() => startEdit(p)}>Edit</button>{" "}
                                        <button onClick={() => handleDelete(p.id)}>Delete</button>
                                    </>
                                )}
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}