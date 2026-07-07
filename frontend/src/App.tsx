import { Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import GetStarted from "./pages/GetStarted";
import Login from "./pages/Login";
import Datasets from "./pages/Datasets";
import Train from "./pages/Train";
import Models from "./pages/Models";
import Compare from "./pages/Compare";
import Signup from "./pages/Signup";
import DatasetDetail from "./pages/DatasetDetail";

// App skeleton: login and signup render bare; every authenticated page is
// guarded by ProtectedRoute and rendered inside the sidebar shell (Layout),
// swapping by URL via the shell's Outlet.
export default function App() {
  return (
    <Routes>
      {/* Public: no shell. */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {/* Authenticated: guarded, then rendered inside the sidebar shell.
          ProtectedRoute bounces guests; Layout provides the sidebar + Outlet. */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Navigate to="/get-started" replace />} />
        <Route path="/get-started" element={<GetStarted />} />
        <Route path="/datasets" element={<Datasets />} />
        <Route path="/datasets/:datasetId" element={<DatasetDetail />} />
        <Route path="/train" element={<Train />} />
        <Route path="/models" element={<Models />} />
        <Route path="/compare" element={<Compare />} />
      </Route>
    </Routes>
  );
}