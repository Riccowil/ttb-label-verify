export default function TabBar({ tabs, activeTab, onChange }) {
  return (
    <nav className="tab-bar" aria-label="Verification mode">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`tab-bar__tab${tab.id === activeTab ? " tab-bar__tab--active" : ""}`}
          onClick={() => onChange(tab.id)}
          aria-current={tab.id === activeTab ? "page" : undefined}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
