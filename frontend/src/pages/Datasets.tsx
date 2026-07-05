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

    // Edit state: which row is being edited, and the draft values in its form.
    // editingId === null means no row is in edit mode.
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editName, setEditName] = useState("");
    const [editDescription, setEditDescription] = useState("");

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

    // Enter edit mode for a row: pre-fill the draft fields with its current values.
    function startEdit(d: Dataset) {
        setEditingId(d.id);
        setEditName(d.name);
        setEditDescription(d.description ?? "");
        setError(null);
    }

    function cancelEdit() {
        setEditingId(null);
    }

    async function handleSave(id: number) {
        setError(null);
        try {
            const updated = await apiFetch<Dataset>(`/datasets/${id}`, {
                method: "PUT",
                body: { name: editName, description: editDescription || null },
            });
            // Swap the updated dataset into state in place, keeping list order.
            setDatasets((prev) => prev.map((d) => (d.id === id ? updated : d)));
            setEditingId(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Update failed");
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
                            {editingId === d.id ? (
                                <>
                                    <input
                                        value={editName}
                                        onChange={(e) => setEditName(e.target.value)}
                                    />
                                    <input
                                        value={editDescription}
                                        onChange={(e) => setEditDescription(e.target.value)}
                                    />
                                    <button onClick={() => handleSave(d.id)}>Save</button>
                                    <button onClick={cancelEdit}>Cancel</button>
                                </>
                            ) : (
                                <>
                                    {d.name} — {d.description ?? "no description"} ({d.source}){" "}
                                    <button onClick={() => startEdit(d)}>Edit</button>{" "}
                                    <button onClick={() => handleDelete(d.id)}>Delete</button>
                                </>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}