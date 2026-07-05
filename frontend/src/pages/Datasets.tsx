import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, clearToken } from "../api";
import type { Dataset } from "../types";

// Datasets: read (list) + create + delete. Each mutation updates local state so
// the list re-renders immediately, no refetch and no page reload.
export default function Datasets() {
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Create-form state
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [source, setSource] = useState("manual");
    const [creating, setCreating] = useState(false);

    const navigate = useNavigate();

    // useEffect with an empty dependency array [] runs once, after first render.
    // This is where a screen loads its data. The token rides along via apiFetch.
    useEffect(() => {
        apiFetch<Dataset[]>("/datasets")
            .then((data) => setDatasets(data))
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
            .finally(() => setLoading(false));
    }, []);

    function handleLogout() {
        clearToken();
        navigate("/login");
    }

    async function handleCreate(e: React.FormEvent) {
        e.preventDefault();
        setCreating(true);
        setError(null);
        try {
            const created = await apiFetch<Dataset>("/datasets", {
                method: "POST",
                body: { name, description: description || null, source },
            });
            // Prepend the new dataset to state -> list re-renders with it on top.
            setDatasets((prev) => [created, ...prev]);
            setName("");
            setDescription("");
            setSource("manual");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Create failed");
        } finally {
            setCreating(false);
        }
    }

    async function handleDelete(id: number) {
        // No confirm dialog yet: native window.confirm is banned (unstyleable, fails
        // WCAG). A styled <ConfirmDialog> component replaces this in the styling pass.
        setError(null);
        try {
            await apiFetch<null>(`/datasets/${id}`, { method: "DELETE" });
            setDatasets((prev) => prev.filter((d) => d.id !== id));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
        }
    }

    return (
        <div>
            <div>
                <h1>Datasets</h1>
                <button onClick={handleLogout}>Log out</button>
            </div>

            <form onSubmit={handleCreate}>
                <input
                    placeholder="Dataset name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                />
                <input
                    placeholder="Description (optional)"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                />
                <select value={source} onChange={(e) => setSource(e.target.value)}>
                    <option value="manual">manual</option>
                    <option value="generated">generated</option>
                    <option value="imported">imported</option>
                </select>
                <button type="submit" disabled={creating}>
                    {creating ? "Creating..." : "Create dataset"}
                </button>
            </form>

            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}

            {!loading && !error && datasets.length === 0 && <p>No datasets yet.</p>}

            {!loading && !error && datasets.length > 0 && (
                <ul>
                    {datasets.map((d) => (
                        <li key={d.id}>
                            {d.name} — {d.description ?? "no description"} ({d.source}){" "}
                            <button onClick={() => handleDelete(d.id)}>Delete</button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}