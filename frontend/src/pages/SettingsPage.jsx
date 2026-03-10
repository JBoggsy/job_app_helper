import { useState, useEffect } from "react";
import { fetchConfig, updateConfig, testConnection, fetchProviders } from "../api";
import ModelCombobox from "../components/ModelCombobox";
import { useAppContext } from "../contexts/AppContext";

const API_KEY_GUIDES = {
  anthropic: {
    label: "Anthropic",
    url: "https://console.anthropic.com/settings/keys",
    steps: [
      "Go to console.anthropic.com and sign in",
      "Click 'API Keys' in the left sidebar",
      "Click '+ Create Key', name it, and copy the key",
    ],
  },
  openai: {
    label: "OpenAI",
    url: "https://platform.openai.com/api-keys",
    steps: [
      "Go to platform.openai.com and sign in",
      "Click 'API keys' in the left sidebar",
      "Click '+ Create new secret key' and copy it immediately — won't be shown again",
    ],
  },
  gemini: {
    label: "Google AI Studio",
    url: "https://aistudio.google.com/app/apikey",
    steps: [
      "Go to aistudio.google.com and sign in with your Google account",
      "Click 'Get API Key' in the left panel",
      "Select or create a Google Cloud project, then click 'Create API key' and copy it",
    ],
  },
  tavily: {
    label: "Tavily",
    url: "https://app.tavily.com/",
    steps: [
      "Go to app.tavily.com and sign up for a free account",
      "After sign-in, your API key is shown on the dashboard",
      "Free tier includes 1,000 searches/month",
    ],
  },
  jsearch: {
    label: "RapidAPI",
    url: "https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch",
    steps: [
      "Go to rapidapi.com and sign up for a free account",
      "Subscribe to the APIs you want — JSearch, Active Jobs DB, and/or LinkedIn Job Search",
      "Copy your 'X-RapidAPI-Key' shown in any API's code examples panel (same key works for all)",
    ],
  },
};

function ApiKeyGuide({ guideKey }) {
  const guide = API_KEY_GUIDES[guideKey];
  if (!guide) return null;
  return (
    <details className="mt-2">
      <summary className="text-xs text-blue-600 cursor-pointer select-none hover:text-blue-800">
        How do I get this key? &#9656;
      </summary>
      <div className="bg-blue-50 rounded-lg p-3 mt-2 text-xs text-gray-700 space-y-2">
        <ol className="list-decimal list-inside space-y-1">
          {guide.steps.map((s, i) => <li key={i}>{s}</li>)}
        </ol>
        <a href={guide.url} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-1 text-blue-600 hover:underline font-medium">
          Open {guide.label} &rarr;
        </a>
      </div>
    </details>
  );
}

export default function SettingsPage({ onSaved }) {
  const { addToast } = useAppContext();
  const [config, setConfig] = useState(null);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);
  const [errors, setErrors] = useState({});

  // Form state
  const [llmProvider, setLlmProvider] = useState("anthropic");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [onboardingProvider, setOnboardingProvider] = useState("");
  const [onboardingApiKey, setOnboardingApiKey] = useState("");
  const [onboardingModel, setOnboardingModel] = useState("");
  const [searchLlmProvider, setSearchLlmProvider] = useState("");
  const [searchLlmApiKey, setSearchLlmApiKey] = useState("");
  const [searchLlmModel, setSearchLlmModel] = useState("");
  const [searchApiKey, setSearchApiKey] = useState("");
  const [jsearchApiKey, setJsearchApiKey] = useState("");
  const [agentMode, setAgentMode] = useState("default");
  const [freeformProvider, setFreeformProvider] = useState("");
  const [freeformApiKey, setFreeformApiKey] = useState("");
  const [freeformModel, setFreeformModel] = useState("");
  const [orchestratedProvider, setOrchestratedProvider] = useState("");
  const [orchestratedApiKey, setOrchestratedApiKey] = useState("");
  const [orchestratedModel, setOrchestratedModel] = useState("");

  useEffect(() => {
    loadConfig();
    loadProviders();
  }, []);

  async function loadConfig() {
    try {
      setLoading(true);
      const data = await fetchConfig();
      setConfig(data);

      setLlmProvider(data.llm?.provider || "anthropic");
      setLlmApiKey(data.llm?.api_key || "");
      setLlmModel(data.llm?.model || "");
      setOnboardingProvider(data.onboarding_llm?.provider || "");
      setOnboardingApiKey(data.onboarding_llm?.api_key || "");
      setOnboardingModel(data.onboarding_llm?.model || "");
      setSearchLlmProvider(data.search_llm?.provider || "");
      setSearchLlmApiKey(data.search_llm?.api_key || "");
      setSearchLlmModel(data.search_llm?.model || "");
      setSearchApiKey(data.integrations?.search_api_key || "");
      setJsearchApiKey(data.integrations?.rapidapi_key || data.integrations?.jsearch_api_key || "");
      setAgentMode(data.agent?.design || "default");
      setFreeformProvider(data.agent?.freeform_llm?.provider || "");
      setFreeformApiKey(data.agent?.freeform_llm?.api_key || "");
      setFreeformModel(data.agent?.freeform_llm?.model || "");
      setOrchestratedProvider(data.agent?.orchestrated_llm?.provider || "");
      setOrchestratedApiKey(data.agent?.orchestrated_llm?.api_key || "");
      setOrchestratedModel(data.agent?.orchestrated_llm?.model || "");
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  }

  async function loadProviders() {
    try {
      const data = await fetchProviders();
      setProviders(data);
    } catch (err) {
      console.error("Failed to load providers:", err);
    }
  }

  async function handleSave() {
    try {
      setSaving(true);
      setMessage(null);
      setErrors({});

      const updatedConfig = {
        llm: { provider: llmProvider, api_key: llmApiKey, model: llmModel },
        onboarding_llm: { provider: onboardingProvider, api_key: onboardingApiKey, model: onboardingModel },
        search_llm: { provider: searchLlmProvider, api_key: searchLlmApiKey, model: searchLlmModel },
        agent: {
          design: agentMode,
          freeform_llm: { provider: freeformProvider, api_key: freeformApiKey, model: freeformModel },
          orchestrated_llm: { provider: orchestratedProvider, api_key: orchestratedApiKey, model: orchestratedModel },
        },
        integrations: { search_api_key: searchApiKey, rapidapi_key: jsearchApiKey },
      };

      await updateConfig(updatedConfig);
      setMessage({ type: "success", text: "Settings saved successfully!" });
      setTimeout(() => loadConfig(), 1000);
      if (onSaved) onSaved();
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleTestConnection() {
    try {
      setTesting(true);
      setMessage(null);

      if (!llmProvider) {
        setErrors({ llmProvider: "Provider is required" });
        return;
      }
      if (!llmApiKey && llmProvider !== "ollama") {
        setErrors({ llmApiKey: "API key is required" });
        return;
      }

      const result = await testConnection(llmProvider, llmApiKey, llmModel);
      if (result.success) {
        setMessage({ type: "success", text: result.message });
        setErrors({});
      }
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setTesting(false);
    }
  }

  const selectedProvider = providers.find((p) => p.id === llmProvider);

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading settings...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <button
          onClick={handleSave}
          disabled={saving || loading}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>

      {/* Message */}
      {message && (
        <div className={`p-4 rounded-lg ${
          message.type === "success"
            ? "bg-green-50 text-green-800 border border-green-200"
            : "bg-red-50 text-red-800 border border-red-200"
        }`}>
          {message.text}
        </div>
      )}

      {/* LLM Configuration */}
      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">AI Assistant (LLM)</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Provider *</label>
            <select
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.llmProvider ? "border-red-500" : "border-gray-300"
              }`}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {selectedProvider && (
              <p className="mt-1 text-xs text-gray-500">
                Default model: {selectedProvider.default_model}
                {!selectedProvider.requires_api_key && " - No API key required"}
              </p>
            )}
            {errors.llmProvider && <p className="mt-1 text-sm text-red-600">{errors.llmProvider}</p>}
          </div>

          {selectedProvider?.requires_api_key && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key *</label>
              <input
                type="password"
                value={llmApiKey}
                onChange={(e) => setLlmApiKey(e.target.value)}
                placeholder="your-api-key-here"
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm ${
                  errors.llmApiKey ? "border-red-500" : "border-gray-300"
                }`}
              />
              {errors.llmApiKey && <p className="mt-1 text-sm text-red-600">{errors.llmApiKey}</p>}
              <ApiKeyGuide guideKey={llmProvider} />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Model Override (optional)</label>
            <ModelCombobox
              provider={llmProvider}
              apiKey={llmApiKey}
              value={llmModel}
              onChange={setLlmModel}
              placeholder={selectedProvider?.default_model || ""}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="mt-1 text-xs text-gray-500">Leave empty to use the default model</p>
          </div>

          <button
            onClick={handleTestConnection}
            disabled={testing}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testing ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </section>

      {/* Agent Mode */}
      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Agent Mode</h2>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setAgentMode("default")}
            className={`p-4 rounded-lg border-2 text-left transition-colors ${
              agentMode === "default" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <div className="font-medium text-gray-900">Freeform</div>
            <p className="text-xs text-gray-500 mt-1">Agent has full control over its reasoning. Best with powerful SOTA models (Claude, GPT-4o, Gemini Pro).</p>
          </button>
          <button
            type="button"
            onClick={() => setAgentMode("micro_agents_v1")}
            className={`p-4 rounded-lg border-2 text-left transition-colors ${
              agentMode === "micro_agents_v1" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <div className="font-medium text-gray-900">Orchestrated</div>
            <p className="text-xs text-gray-500 mt-1">Structured pipeline guides the agent step by step. Works well with cheaper or local models (GPT-4o-mini, Gemini Flash, Ollama).</p>
          </button>
        </div>

        <details className="mt-2">
          <summary className="text-sm font-medium text-gray-700 cursor-pointer select-none">
            Per-mode model overrides <span className="text-xs font-normal text-gray-500">(Optional)</span>
          </summary>
          <div className="mt-3 space-y-5">
            <p className="text-sm text-gray-600">
              Optionally set a different provider/model for each mode. When switching modes, the override for that mode will be used automatically. Leave blank to use the main AI Assistant configuration above.
            </p>

            {/* Freeform overrides */}
            <div className="space-y-3 p-3 bg-gray-50 rounded-lg">
              <div className="text-sm font-medium text-gray-800">Freeform mode</div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Provider</label>
                <select value={freeformProvider} onChange={(e) => setFreeformProvider(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm">
                  <option value="">Same as above</option>
                  {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input type="password" value={freeformApiKey} onChange={(e) => setFreeformApiKey(e.target.value)}
                  placeholder="Leave blank to use the same key as above"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Model</label>
                <ModelCombobox provider={freeformProvider || llmProvider} apiKey={freeformApiKey || llmApiKey}
                  value={freeformModel} onChange={setFreeformModel} placeholder="Leave blank to use the provider default"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
              </div>
            </div>

            {/* Orchestrated overrides */}
            <div className="space-y-3 p-3 bg-gray-50 rounded-lg">
              <div className="text-sm font-medium text-gray-800">Orchestrated mode</div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Provider</label>
                <select value={orchestratedProvider} onChange={(e) => setOrchestratedProvider(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm">
                  <option value="">Same as above</option>
                  {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input type="password" value={orchestratedApiKey} onChange={(e) => setOrchestratedApiKey(e.target.value)}
                  placeholder="Leave blank to use the same key as above"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Model</label>
                <ModelCombobox provider={orchestratedProvider || llmProvider} apiKey={orchestratedApiKey || llmApiKey}
                  value={orchestratedModel} onChange={setOrchestratedModel} placeholder="Leave blank to use the provider default"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
              </div>
            </div>
          </div>
        </details>
      </section>

      {/* Onboarding Agent */}
      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <details>
          <summary className="text-lg font-semibold text-gray-900 cursor-pointer select-none">
            Onboarding Agent <span className="text-sm font-normal text-gray-500">(Optional)</span>
          </summary>
          <div className="mt-3 space-y-4">
            <p className="text-sm text-gray-600">
              Uses a separate model for the one-time onboarding interview. Leave blank to use the same AI Assistant configuration above. A cheaper model is recommended here to save costs.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <select value={onboardingProvider} onChange={(e) => setOnboardingProvider(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                <option value="">Same as above</option>
                {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input type="password" value={onboardingApiKey} onChange={(e) => setOnboardingApiKey(e.target.value)}
                placeholder="Leave blank to use the same key as above"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Override (optional)</label>
              <ModelCombobox provider={onboardingProvider || llmProvider} apiKey={onboardingApiKey || llmApiKey}
                value={onboardingModel} onChange={setOnboardingModel} placeholder="Leave blank to use the provider default"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
          </div>
        </details>
      </section>

      {/* Search Sub-Agent */}
      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <details>
          <summary className="text-lg font-semibold text-gray-900 cursor-pointer select-none">
            Job Search Agent <span className="text-sm font-normal text-gray-500">(Optional)</span>
          </summary>
          <div className="mt-3 space-y-4">
            <p className="text-sm text-gray-600">
              Uses a separate model for the job search sub-agent that finds and evaluates job listings. Leave blank to use the same AI Assistant configuration above. A cheaper model is recommended to reduce costs during searches.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <select value={searchLlmProvider} onChange={(e) => setSearchLlmProvider(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                <option value="">Same as above</option>
                {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input type="password" value={searchLlmApiKey} onChange={(e) => setSearchLlmApiKey(e.target.value)}
                placeholder="Leave blank to use the same key as above"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Override (optional)</label>
              <ModelCombobox provider={searchLlmProvider || llmProvider} apiKey={searchLlmApiKey || llmApiKey}
                value={searchLlmModel} onChange={setSearchLlmModel} placeholder="Leave blank to use the provider default"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
          </div>
        </details>
      </section>

      {/* Integrations */}
      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Integrations</h2>
        <p className="text-sm text-gray-600">
          These keys give the AI assistant extra capabilities. Tavily is recommended — it's required for web search, the assistant's most useful feature.
        </p>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tavily Search API Key
              <span className="ml-2 inline-block px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded">Recommended</span>
            </label>
            <input type="password" value={searchApiKey} onChange={(e) => setSearchApiKey(e.target.value)}
              placeholder="tvly-..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm" />
            <p className="mt-1 text-xs text-gray-500">
              Required for the AI to search the web. Without this, the assistant can only read URLs you paste directly. Free tier: 1,000 searches/month at tavily.com
            </p>
            <ApiKeyGuide guideKey="tavily" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">RapidAPI Key</label>
            <input type="password" value={jsearchApiKey} onChange={(e) => setJsearchApiKey(e.target.value)}
              placeholder="Your RapidAPI key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm" />
            <p className="mt-1 text-xs text-gray-500">
              Enables searching job boards from the AI assistant. One key works for all subscribed providers: JSearch (Indeed, LinkedIn), Active Jobs DB (170k+ company career sites), and LinkedIn Job Search.
            </p>
            <ApiKeyGuide guideKey="jsearch" />
          </div>
        </div>
      </section>

      {/* Bottom save button */}
      <div className="flex justify-end pb-8">
        <button
          onClick={handleSave}
          disabled={saving || loading}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
