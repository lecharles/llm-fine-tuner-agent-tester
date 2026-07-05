import { Routes, Route, Navigate } from "react-router-dom";
import Nav from "./components/Nav";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Datasets from "./pages/Datasets";
import Train from "./pages/Train";
import Models from "./pages/Models";
import Compare from "./pages/Compare";

// App skeleton: the nav is always on screen; the routes below swap by URL.
// Protected pages are wrapped in ProtectedRoute, which bounces guests to /login.
export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<Navigate to="/datasets" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/datasets" element={<ProtectedRoute><Datasets /></ProtectedRoute>} />
        <Route path="/train" element={<ProtectedRoute><Train /></ProtectedRoute>} />
        <Route path="/models" element={<ProtectedRoute><Models /></ProtectedRoute>} />
        <Route path="/compare" element={<ProtectedRoute><Compare /></ProtectedRoute>} />
      </Routes>
    </>
  );
}