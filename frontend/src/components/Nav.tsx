import { Link } from "react-router-dom";

// The app's navigation. Plain <Link>s: they change the view without a full
// page reload (client-side routing). Styling comes at the very end.
export default function Nav() {
    return (
        <nav>
            <Link to="/datasets">Datasets</Link>
            {" | "}
            <Link to="/train">Train</Link>
            {" | "}
            <Link to="/models">Models</Link>
            {" | "}
            <Link to="/compare">Compare</Link>
        </nav>
    );
}