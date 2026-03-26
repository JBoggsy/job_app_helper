import { useState, useEffect } from 'react';
import { updateConfig, testConnection } from '../api';
import ModelCombobox from './ModelCombobox';

const PROVIDERS = [
  {
    id: "anthropic",
    name: "Anthropic",
    subtitle: "Claude",
    desc: "Powerful and reliable",
    badge: "Recommended",
    badgeColor: "bg-blue-100 text-blue-700",
    requiresKey: true,
    url: "https://console.anthropic.com/settings/keys",
    steps: [
      "Go to console.anthropic.com and sign in",
      "Click 'API Keys' in the sidebar",
      "Click '+ Create Key' and copy it",
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    subtitle: "GPT",
    desc: "Popular choice",
    badge: null,
    requiresKey: true,
    url: "https://platform.openai.com/api-keys",
    steps: [
      "Go to platform.openai.com and sign in",
      "Click 'API keys' in the sidebar",
      "Click '+ Create new secret key' and copy immediately",
    ],
  },
  {
    id: "gemini",
    name: "Google",
    subtitle: "Gemini",
    desc: "Google's AI",
    badge: null,
    requiresKey: true,
    url: "https://aistudio.google.com/app/apikey",
    steps: [
      "Go to aistudio.google.com and sign in",
      "Click 'Get API Key'",
      "Select/create a project and copy the key",
    ],
  },
  {
    id: "ollama",
    name: "Ollama",
    subtitle: "Local",
    desc: "No key needed — runs on your machine",
    badge: "Free",
    badgeColor: "bg-green-100 text-green-700",
    requiresKey: false,
    url: "https://ollama.com/",
    steps: [
      "Download Ollama from ollama.com",
      "Run 'ollama pull <model>' (e.g. llama3.1, qwen3, gemma3)",
      "Ensure Ollama is running before testing",
    ],
  },
];

const INTEGRATION_KEYS = [
  {
    id: "tavily",
    label: "Tavily Search API Key",
    badge: "Recommended",
    badgeColor: "bg-amber-100 text-amber-700",
    placeholder: "tvly-...",
    description: "Enables web search — the assistant's most useful feature. Without this, the assistant can only read URLs you paste directly.",
    freeNote: "Free tier: 1,000 searches/month",
    url: "https://app.tavily.com/",
    steps: [
      "Go to app.tavily.com and sign up for a free account",
      "After sign-in, your API key is shown on the dashboard",
      "Copy the key and paste it here",
    ],
  },
  {
    id: "jsearch",
    label: "RapidAPI Key",
    badge: null,
    placeholder: "Your RapidAPI key",
    description: "Enables searching job boards from the AI assistant. One key works for JSearch, Active Jobs DB, and LinkedIn Job Search.",
    freeNote: "Free tier available on RapidAPI",
    url: "https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch",
    steps: [
      "Go to rapidapi.com and sign up for a free account",
      "Subscribe to the job search APIs you want (JSearch, Active Jobs DB, LinkedIn Job Search)",
      "Copy your 'X-RapidAPI-Key' from any API's code examples panel",
    ],
  },
];

const TOTAL_STEPS = 5;

export default function SetupWizard({ isOpen, onClose, onComplete }) {
  const [step, setStep] = useState(1);
  const [selectedProvider, setSelectedProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [testStatus, setTestStatus] = useState(null); // null | "testing" | "success" | "error"
  const [testMessage, setTestMessage] = useState("");
  const [testErrorType, setTestErrorType] = useState(null);
  const [saving, setSaving] = useState(false);
  const [tavilyKey, setTavilyKey] = useState("");
  const [jsearchKey, setJsearchKey] = useState("");

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setSelectedProvider("anthropic");
      setApiKey("");
      setModel("");
      setTestStatus(null);
      setTestMessage("");
      setTestErrorType(null);
      setSaving(false);
      setTavilyKey("");
      setJsearchKey("");
    }
  }, [isOpen]);

  function handleProviderSelect(id) {
    setSelectedProvider(id);
    setApiKey("");
    setTestStatus(null);
    setTestMessage("");
    setTestErrorType(null);
  }

  async function handleTest() {
    setTestStatus("testing");
    setTestMessage("");
    setTestErrorType(null);
    try {
      const r = await testConnection(selectedProvider, apiKey, model);
      setTestStatus("success");
      setTestMessage(r.message || "Connection successful!");
    } catch (e) {
      setTestStatus("error");
      setTestMessage(e.message || "Connection failed.");
      setTestErrorType(e.errorType || null);
    }
  }

  async function handleContinue() {
    if (step === 4) {
      // Save all config (LLM + integrations) when leaving the integrations step
      setSaving(true);
      try {
        const configPayload = {
          llm: { provider: selectedProvider, api_key: apiKey, model },
          integrations: {
            search_api_key: tavilyKey,
            rapidapi_key: jsearchKey,
          },
        };
        await updateConfig(configPayload);
        setStep(5);
      } catch (e) {
        setTestStatus("error");
        setTestMessage("Failed to save: " + (e.message || "Unknown error"));
      } finally {
        setSaving(false);
      }
      return;
    }
    setStep((s) => s + 1);
  }

  function canContinue() {
    if (step === 1 || step === 2 || step === 4) return true;
    if (step !== 3) return false;
    const p = PROVIDERS.find((p) => p.id === selectedProvider);
    if (!p.requiresKey) return true;
    return testStatus === "success";
  }

  if (!isOpen) return null;

  const provider = PROVIDERS.find((p) => p.id === selectedProvider);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div
        className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl flex flex-col"
        style={{ minHeight: "480px" }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 text-2xl font-light leading-none z-10"
          aria-label="Close"
        >
          ×
        </button>

        {/* Progress dots */}
        <div className="flex justify-center gap-2 pt-6 pb-2">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map((dot) => (
            <div
              key={dot}
              className={`rounded-full transition-colors ${
                dot === step
                  ? "w-3 h-3 bg-blue-600"
                  : dot < step
                  ? "w-3 h-3 bg-blue-300"
                  : "w-3 h-3 bg-gray-200"
              }`}
            />
          ))}
        </div>

        {/* Step content */}
        <div className="flex-1 px-8 py-4 flex flex-col">
          {step === 1 && <StepWelcome />}
          {step === 2 && (
            <StepChooseProvider
              selectedProvider={selectedProvider}
              onSelect={handleProviderSelect}
            />
          )}
          {step === 3 && (
            <StepEnterKey
              provider={provider}
              apiKey={apiKey}
              setApiKey={setApiKey}
              model={model}
              setModel={setModel}
              testStatus={testStatus}
              testMessage={testMessage}
              testErrorType={testErrorType}
              onTest={handleTest}
            />
          )}
          {step === 4 && (
            <StepIntegrations
              tavilyKey={tavilyKey}
              setTavilyKey={setTavilyKey}
              jsearchKey={jsearchKey}
              setJsearchKey={setJsearchKey}
            />
          )}
          {step === 5 && (
            <StepDone onComplete={onComplete} onClose={onClose} />
          )}
        </div>

        {/* Nav footer (hidden on final step) */}
        {step !== TOTAL_STEPS && (
          <div className="flex items-center justify-between px-8 pb-6 pt-2">
            <button
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              className={`text-gray-500 hover:text-gray-700 text-sm ${
                step === 1 ? "invisible" : ""
              }`}
            >
              ← Back
            </button>
            <button
              onClick={handleContinue}
              disabled={!canContinue() || saving}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
            >
              {saving ? "Saving..." : step === 4 ? "Save & Continue →" : "Continue →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function StepWelcome() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 text-center gap-4">
      <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
        <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-gray-900">Welcome to Shortlist</h2>
      <p className="text-gray-600 max-w-sm">
        Track your job applications and get AI-powered help with research, job searching, and more.
        Let's get you set up in a minute.
      </p>
    </div>
  );
}

function StepChooseProvider({ selectedProvider, onSelect }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Choose your AI provider</h2>
        <p className="text-sm text-gray-500 mt-1">
          The AI assistant powers job research and chat. Pick one to get started.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {PROVIDERS.map((p) => (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            className={`text-left p-4 rounded-xl border-2 transition-colors ${
              selectedProvider === p.id
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 hover:border-gray-300 bg-white"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-gray-900">{p.name}</div>
                <div className="text-xs text-gray-500">{p.subtitle}</div>
              </div>
              {p.badge && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${p.badgeColor}`}>
                  {p.badge}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-600 mt-2">{p.desc}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

function StepEnterKey({ provider, apiKey, setApiKey, model, setModel, testStatus, testMessage, testErrorType, onTest }) {
  if (!provider) return null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900">
          {provider.requiresKey ? `Enter your ${provider.name} API key` : `Set up ${provider.name}`}
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          {provider.requiresKey
            ? "You'll need an API key to use this provider."
            : "Ollama runs locally — no API key required."}
        </p>
      </div>

      {/* How-to guide (always visible) */}
      <div className="bg-blue-50 rounded-lg p-3 text-xs text-gray-700 space-y-2">
        <p className="font-medium text-gray-800">How to get set up:</p>
        <ol className="list-decimal list-inside space-y-1">
          {provider.steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
        <a
          href={provider.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-blue-600 hover:underline font-medium"
        >
          Open {provider.name} →
        </a>
      </div>

      {/* API key input */}
      {provider.requiresKey && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Paste your API key here"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
          />
        </div>
      )}

      {/* Model override */}
      <details>
        <summary className="text-xs text-gray-500 cursor-pointer select-none hover:text-gray-700">
          Advanced: model override
        </summary>
        <div className="mt-2">
          <ModelCombobox
            provider={provider.id}
            apiKey={apiKey}
            value={model}
            onChange={setModel}
            placeholder="Leave blank for default model"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>
      </details>

      {/* Test connection */}
      <div className="flex items-center gap-3">
        <button
          onClick={onTest}
          disabled={testStatus === "testing" || (provider.requiresKey && !apiKey)}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium"
        >
          {testStatus === "testing" ? "Testing..." : "Test Connection"}
        </button>
        {testStatus === "success" && (
          <span className="text-sm text-green-600 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {testMessage}
          </span>
        )}
        {testStatus === "error" && (
          <div className="text-sm text-red-600 space-y-1">
            <span>{testMessage}</span>
            {testErrorType === "model_not_found" && (
              <p className="text-xs text-gray-500">
                Tip: expand "Advanced: model override" below to pick an installed model.
              </p>
            )}
          </div>
        )}
      </div>

      {provider.requiresKey && testStatus !== "success" && (
        <p className="text-xs text-gray-400">Test the connection to continue.</p>
      )}
    </div>
  );
}

function StepIntegrations({ tavilyKey, setTavilyKey, jsearchKey, setJsearchKey }) {
  const setters = { tavily: setTavilyKey, jsearch: setJsearchKey };
  const values = { tavily: tavilyKey, jsearch: jsearchKey };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Add search integrations</h2>
        <p className="text-sm text-gray-500 mt-1">
          These free API keys unlock the assistant's best features. You can skip this and add them later in Settings.
        </p>
      </div>

      <div className="space-y-4 overflow-y-auto" style={{ maxHeight: "320px" }}>
        {INTEGRATION_KEYS.map((integration) => (
          <div key={integration.id} className="border border-gray-200 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-gray-900">{integration.label}</span>
              {integration.badge && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${integration.badgeColor}`}>
                  {integration.badge}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-600">{integration.description}</p>

            {/* How-to guide (always visible) */}
            <div className="bg-blue-50 rounded-lg p-3 text-xs text-gray-700 space-y-2">
              <p className="font-medium text-gray-800">How to get this key:</p>
              <ol className="list-decimal list-inside space-y-1">
                {integration.steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
              <a
                href={integration.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline font-medium"
              >
                Open {integration.label.split(" (")[0]} →
              </a>
              {integration.freeNote && (
                <p className="text-gray-500">{integration.freeNote}</p>
              )}
            </div>

            <input
              type="password"
              value={values[integration.id]}
              onChange={(e) => setters[integration.id](e.target.value)}
              placeholder={integration.placeholder}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function StepDone({ onComplete, onClose }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 text-center gap-4">
      <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
        <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-gray-900">You're all set!</h2>
      <p className="text-gray-600 max-w-sm">
        Next, a quick AI interview will build your job search profile so the assistant can give you
        personalized help.
      </p>
      <button
        onClick={onComplete}
        className="mt-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
      >
        Meet Your AI Assistant →
      </button>
      <button
        onClick={onClose}
        className="text-sm text-gray-400 hover:text-gray-600"
      >
        Skip for now
      </button>
    </div>
  );
}
