/**
 * Maps raw LLM/backend error strings to user-friendly toast messages.
 *
 * Each matcher returns { title, message, detail? } or null if it doesn't match.
 * The first matcher that returns non-null wins.
 *
 * `detail` is the raw error string, shown behind a collapsible toggle.
 */

const ERROR_MATCHERS = [
  // --- Authentication / API key errors ---
  {
    test: (msg) =>
      /invalid.*api.?key|invalid.*x-api-key|incorrect.*api.?key|authentication|unauthorized|401/i.test(msg),
    result: () => ({
      title: "Invalid API Key",
      message:
        "Your API key was rejected by the provider. Open Settings and double-check that you've pasted the correct key.",
    }),
  },
  {
    test: (msg) => /permission|forbidden|403/i.test(msg) && !/rate/i.test(msg),
    result: () => ({
      title: "Access Denied",
      message:
        "Your API key doesn't have permission to use this model. Check your provider account to ensure the key has the required access level.",
    }),
  },

  // --- Quota / billing errors ---
  {
    test: (msg) =>
      /insufficient.?quota|billing|payment|exceeded.*quota|quota.*exceeded|credits?.*exhaust|out of credits|budget/i.test(msg),
    result: () => ({
      title: "Out of Credits",
      message:
        "Your LLM provider account has run out of credits or has a billing issue. Add credits or update your payment method on your provider's website, then try again.",
    }),
  },

  // --- Rate limiting ---
  {
    test: (msg) => /rate.?limit|too.?many.?requests|429|throttl/i.test(msg),
    result: () => ({
      title: "Rate Limited",
      message:
        "Too many requests — the provider is asking you to slow down. Wait a moment and try again.",
    }),
  },

  // --- Model not found ---
  {
    test: (msg) =>
      /model.*not.?found|does.?not.?exist|invalid.*model|unknown.*model|no such model|404.*model|model.*404/i.test(msg),
    result: () => ({
      title: "Model Not Found",
      message:
        "The selected model doesn't exist or isn't available on your account. Open Settings and choose a different model.",
    }),
  },

  // --- Content / safety filters ---
  {
    test: (msg) =>
      /content.?filter|safety|blocked|moderation|harmful|policy/i.test(msg),
    result: () => ({
      title: "Content Blocked",
      message:
        "The provider's content filter blocked this request. Try rephrasing your message.",
    }),
  },

  // --- Context length / token limits ---
  {
    test: (msg) =>
      /context.?length|token.?limit|too.?long|maximum.*tokens|max.*tokens|input.*too.*large/i.test(msg),
    result: () => ({
      title: "Message Too Long",
      message:
        "The conversation has grown too long for the model's context window. Start a new chat to continue.",
    }),
  },

  // --- Overloaded / server errors ---
  {
    test: (msg) => /overloaded|capacity|503|service.?unavailable/i.test(msg),
    result: () => ({
      title: "Provider Overloaded",
      message:
        "The LLM provider is currently overloaded. Wait a minute and try again.",
    }),
  },
  {
    test: (msg) => /500|internal.?server.?error|internal.?error/i.test(msg),
    result: () => ({
      title: "Provider Error",
      message:
        "The LLM provider returned an internal server error. This is usually temporary — try again in a moment.",
    }),
  },

  // --- Network / timeout errors ---
  {
    test: (msg) =>
      /timeout|timed?\s?out|ETIMEDOUT|ECONNABORTED/i.test(msg),
    result: () => ({
      title: "Request Timed Out",
      message:
        "The request to the LLM provider timed out. Check your internet connection and try again. If using Ollama, make sure the server is running.",
    }),
  },
  {
    test: (msg) =>
      /ECONNREFUSED|connection.?refused/i.test(msg),
    result: () => ({
      title: "Connection Refused",
      message:
        "Could not connect to the LLM provider. If you're using Ollama, make sure it's running (ollama serve). For cloud providers, check your internet connection.",
    }),
  },
  {
    test: (msg) =>
      /ENOTFOUND|DNS|network|connection.*error|connect.*fail|unreachable|fetch.*fail/i.test(msg),
    result: () => ({
      title: "Connection Error",
      message:
        "Could not reach the LLM provider. Check your internet connection and try again.",
    }),
  },

  // --- LLM not configured ---
  {
    test: (msg) => /not configured|configure.*api.?key|no.*api.?key/i.test(msg),
    result: () => ({
      title: "LLM Not Configured",
      message:
        "No API key is set up. Open Settings (gear icon) and enter your provider's API key to get started.",
    }),
  },

  // --- Max iterations ---
  {
    test: (msg) => /max.?iterations/i.test(msg),
    result: () => ({
      title: "Agent Loop Limit",
      message:
        "The AI assistant reached its maximum number of steps for one response. Try breaking your request into smaller pieces.",
    }),
  },

  // --- Failed to initialize provider ---
  {
    test: (msg) => /failed to initialize|failed to create/i.test(msg),
    result: () => ({
      title: "Provider Setup Failed",
      message:
        "Could not initialize the LLM provider. Open Settings and verify your provider selection and API key.",
    }),
  },
];

/**
 * Classify a raw error message into a user-friendly toast payload.
 *
 * @param {string} rawError — the raw error string from the backend or network
 * @returns {{ type: string, title: string, message: string, detail?: string }}
 */
export function classifyError(rawError) {
  const msg = rawError || "Unknown error";

  for (const matcher of ERROR_MATCHERS) {
    if (matcher.test(msg)) {
      return {
        type: "error",
        ...matcher.result(),
        detail: msg,
      };
    }
  }

  // Fallback — unrecognised error
  return {
    type: "error",
    title: "Something Went Wrong",
    message:
      "An unexpected error occurred while communicating with the AI provider. Check Settings to verify your configuration, or try again.",
    detail: msg,
  };
}

/**
 * Classify a network-level fetch failure (e.g. server unreachable).
 *
 * @param {Error} error — the JS Error object from fetch
 * @returns {{ type: string, title: string, message: string, detail?: string }}
 */
export function classifyNetworkError(error) {
  if (!error) {
    return {
      type: "error",
      title: "Connection Lost",
      message: "Lost connection to the backend server. Make sure the app is running and try again.",
    };
  }

  // Try to match it through the normal classifier first
  const classified = classifyError(error.message || String(error));

  // If the classifier gave us the generic fallback, replace with a network-specific one
  if (classified.title === "Something Went Wrong") {
    return {
      type: "error",
      title: "Connection Error",
      message:
        "Failed to reach the backend server. Make sure the app is running and your internet connection is stable.",
      detail: error.message || String(error),
    };
  }

  return classified;
}
