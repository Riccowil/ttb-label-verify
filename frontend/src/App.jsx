import { useState } from "react";
import TabBar from "./components/TabBar.jsx";
import SingleVerifyTab from "./components/SingleVerifyTab.jsx";
import BatchTab from "./components/BatchTab.jsx";
import "./App.css";

const TABS = [
  { id: "single", label: "Verify Label" },
  { id: "batch", label: "Batch" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("single");

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">TTB Label Verify</h1>
        <p className="app-subtitle">Compare a label against its application in seconds.</p>
      </header>

      <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      <main className="app-main" key={activeTab}>
        {activeTab === "single" ? <SingleVerifyTab /> : <BatchTab />}
      </main>
    </div>
  );
}
