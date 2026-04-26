import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import Dashboard from "./pages/Dashboard";
import StateMachine from "./pages/StateMachine";
import Messages from "./pages/Messages";
import EvidenceChain from "./pages/EvidenceChain";
import ProbeHistory from "./pages/ProbeHistory";
import { ProjectProvider } from "./context/ProjectContext";

function App() {
  return (
    <ProjectProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="state-machine" element={<StateMachine />} />
            <Route path="messages" element={<Messages />} />
            <Route path="evidence" element={<EvidenceChain />} />
            <Route path="probes" element={<ProbeHistory />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ProjectProvider>
  );
}

export default App;
