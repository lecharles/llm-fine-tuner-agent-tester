import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, clearToken } from "../api";
import type { Dataset } from "../types";

// Datasets list. Fetches the current user's datasets on mount and renders them.
// This is the Read of CRUD; create/update/delete land in 4b and 4c.
export default function Datasets() {
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
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

    return (
        <div>
            <div>
                <h1>Datasets</h1>
                <button onClick={handleLogout}>Log out</button>
            </div>

            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}

            {!loading && !error && datasets.length === 0 && (
                <p>No datasets yet.</p>
            )}

            {!loading && !error && datasets.length > 0 && (
                <ul>
                    {datasets.map((d) => (
                        <li key={d.id}>
                            {d.name} — {d.description ?? "no description"} ({d.source})
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}