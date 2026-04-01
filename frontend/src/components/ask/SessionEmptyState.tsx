"use client";

const GREETINGS = [
  "Hey there.",
  "Good to see you.",
  "Ready when you are.",
  "Let's get into it.",
];

const ASK_SUGGESTIONS = [
  { text: "How is Marcus doing this month?", icon: "👤" },
  { text: "Which properties have the most turnover?", icon: "🔄" },
  { text: "Are any leases expiring soon?", icon: "📋" },
  { text: "Compare my managers on occupancy", icon: "📊" },
];

const RESEARCH_SUGGESTIONS = [
  { text: "What trends am I missing across all managers?", icon: "📈" },
  { text: "Find which properties are statistically underperforming", icon: "🔍" },
  { text: "Run a full portfolio health analysis", icon: "🩺" },
  { text: "Cluster managers by performance profile", icon: "⚖️" },
];

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning.";
  if (hour < 17) return "Good afternoon.";
  return GREETINGS[Math.floor(Math.random() * GREETINGS.length)];
}

export function SessionEmptyState({
  onSend,
  connected,
  streaming,
  mode,
  managerName,
}: {
  onSend: (text: string) => void;
  connected: boolean;
  streaming: boolean;
  mode: "ask" | "research";
  managerName?: string;
}) {
  const suggestions = managerName
    ? mode === "research"
      ? [
          { text: `What trends are emerging in ${managerName}'s portfolio?`, icon: "📈" },
          { text: `Find statistically underperforming properties for ${managerName}`, icon: "🔍" },
          { text: `Analyze ${managerName}'s maintenance patterns`, icon: "🔧" },
          { text: `How does ${managerName} compare statistically?`, icon: "⚖️" },
        ]
      : [
          { text: `How is ${managerName} doing this month?`, icon: "👤" },
          { text: `Any issues with ${managerName}'s properties?`, icon: "🔄" },
          { text: `What's ${managerName}'s occupancy rate?`, icon: "📊" },
          { text: `Are any of ${managerName}'s leases expiring soon?`, icon: "📋" },
        ]
    : mode === "research"
      ? RESEARCH_SUGGESTIONS
      : ASK_SUGGESTIONS;

  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex flex-col items-center max-w-md w-full px-4 py-16">
        {/* Warm accent mark */}
        <div className="w-10 h-1 rounded-full bg-accent/40 mb-6" />

        <h2 className="text-lg font-medium text-fg mb-1 tracking-tight">
          {getGreeting()}
        </h2>
        <p className="text-sm text-fg-muted mb-10 text-center max-w-xs leading-relaxed">
          {managerName
            ? `Focused on ${managerName}'s portfolio.`
            : mode === "research"
              ? "I'll run statistical analysis and surface what matters."
              : "Ask me anything about your portfolio."}
        </p>

        <div className="grid grid-cols-1 gap-2 w-full">
          {suggestions.map((q) => (
            <button
              key={q.text}
              onClick={() => onSend(q.text)}
              disabled={!connected || streaming}
              className="group text-left px-4 py-3 rounded-xl border border-border text-[13px] text-fg-muted hover:text-fg hover:border-accent/30 hover:bg-accent-soft transition-all disabled:opacity-30 leading-snug flex items-center gap-3"
            >
              <span className="text-base opacity-60 group-hover:opacity-100 transition-opacity">{q.icon}</span>
              <span>{q.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
