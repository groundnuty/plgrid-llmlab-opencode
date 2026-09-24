// PLGrid Forge (ACK Cyfronet) - unofficial opencode provider plugin.
//
// Drop this file into one of:
//   <project>/.opencode/plugins/      - this project only
//   ~/.config/opencode/plugins/       - every project on this machine
// or publish it as an npm package / git repo and reference it from the
// "plugin" array in opencode.json, so colleagues can install it and log in
// with their own PLGrid grant key.
//
// After installing, authenticate once with:
//   opencode providers login -p plgrid
// The key is stored in ~/.local/share/opencode/auth.json - no key ever
// needs to appear in a config file or an environment variable.
//
// Model metadata below is derived from the live gateway, not guessed:
//   tool_call       - PLGrid's function_calling_supported field
//   attachment      - vision-language model (Qwen3-VL)
//   reasoning       - verified by inspecting the streaming/non-streaming
//                     response: the gateway (vLLM 0.29) exposes chain of
//                     thought in the message's "reasoning" field
//   limit.context   - from the server's own max_model_len error messages
//   limit.output    - kept well under context; opencode sends this verbatim
//                     as max_tokens, and the gateway enforces
//                     input + max_tokens <= context
//
// Two caveats:
//   * Some models are reachable only through a grant other than the default
//     one. They list as accessible in /v1/models-plgrid-format but the gateway
//     currently routes requests through a single grant, so they may answer 400
//     until the key is pointed at the right grant.
//   * For those same models the reasoning/limit fields could not be probed
//     from this account, so they are left at opencode's defaults rather
//     than filled in with a guess.
//
// The embedding model (Qwen/Qwen3-Embedding-0.6B) is deliberately absent:
// this provider exposes chat models to opencode, and an embedding model is
// not selectable as one.

const BASE_URL = "https://llmlab.plgrid.pl/api/v1"

const MODELS = {
  "zai-org/GLM-5.2-FP8": {
    "name": "GLM-5.2 FP8 (non-commercial)",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning"
    },
    "limit": {
      "context": 393216,
      "output": 32768
    }
  },
  "zai-org/GLM-5.3-Flash": {
    "name": "GLM-5.3 Flash (non-commercial)",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning"
    },
    "limit": {
      "context": 1048576,
      "output": 32768
    }
  },
  "deepseek-ai/DeepSeek-V4.1-Flash": {
    "name": "DeepSeek V4.1 Flash (non-commercial)",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning"
    },
    "limit": {
      "context": 1048576,
      "output": 32768
    }
  },
  "deepseek-ai/DeepSeek-V4-Flash": {
    "name": "DeepSeek V4 Flash",
    "tool_call": true,
    "limit": {
      "context": 700000,
      "output": 32768
    }
  },
  "deepseek-ai/DeepSeek-V4-Flash-0731": {
    "name": "DeepSeek V4 Flash 0731 (non-commercial)",
    "tool_call": true,
    "limit": {
      "context": 700000,
      "output": 32768
    }
  },
  "Qwen/Qwen3.6-27B": {
    "name": "Qwen3.6 27B (non-commercial)",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning"
    },
    "limit": {
      "context": 262144,
      "output": 32768
    }
  },
  "Qwen/Qwen3.6-35B-A3B": {
    "name": "Qwen3.6 35B A3B",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning"
    },
    "limit": {
      "context": 262144,
      "output": 32768
    }
  },
  "Qwen/Qwen3.8-27B": {
    "name": "Qwen3.8 27B",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning"
    },
    "limit": {
      "context": 262144,
      "output": 32768
    }
  },
  "Qwen/Qwen3.5-397B-A17B-FP8": {
    "name": "Qwen3.5 397B A17B FP8",
    "tool_call": true
  },
  "Qwen/Qwen3.5-122B-A10B": {
    "name": "Qwen3.5 122B A10B",
    "tool_call": true
  },
  "Qwen/Qwen3-Coder-30B-A3B-Instruct": {
    "name": "Qwen3 Coder 30B A3B",
    "tool_call": true,
    "limit": {
      "context": 249600,
      "output": 32768
    }
  },
  "Qwen/Qwen3-VL-8B-Instruct": {
    "name": "Qwen3 VL 8B (vision)",
    "tool_call": false,
    "attachment": true,
    "limit": {
      "context": 262144,
      "output": 32768
    }
  },
  "Qwen/QwQ-32B": {
    "name": "QwQ 32B",
    "tool_call": false,
    "limit": {
      "context": 40960,
      "output": 8192
    }
  },
  "google/gemma-4-31B": {
    "name": "Gemma 4 31B (non-commercial)",
    "tool_call": true,
    "limit": {
      "context": 262144,
      "output": 32768
    }
  },
  "meta-llama/Llama-3.3-70B-Instruct": {
    "name": "Llama 3.3 70B Instruct",
    "tool_call": true,
    "limit": {
      "context": 131072,
      "output": 16384
    }
  },
  "speakleash/Bielik-11B-v3.0-Instruct": {
    "name": "Bielik 11B v3.0",
    "tool_call": true,
    "limit": {
      "context": 32768,
      "output": 4096
    }
  },
  "speakleash/Bielik-11B-v2.6-Instruct": {
    "name": "Bielik 11B v2.6",
    "tool_call": false,
    "limit": {
      "context": 32768,
      "output": 4096
    }
  },
  "CYFRAGOVPL/Llama-PLLuM-70B-chat-250801": {
    "name": "Llama-PLLuM 70B chat",
    "tool_call": false,
    "limit": {
      "context": 131072,
      "output": 16384
    }
  },
  "CYFRAGOVPL/pllum-12b-nc-chat-250715": {
    "name": "PLLuM 12B chat (non-commercial)",
    "tool_call": false,
    "limit": {
      "context": 131072,
      "output": 16384
    }
  }
}

// Merge a user's per-model overrides onto the defaults one model at a time, so
// overriding one model's limit keeps the other models (and that model's other fields).
const mergeModels = (defaults, overrides) => {
  const merged = { ...defaults }
  for (const [id, override] of Object.entries(overrides)) {
    const base = defaults[id] ?? {}
    merged[id] = { ...base, ...override }
    if (base.limit || override.limit) merged[id].limit = { ...base.limit, ...override.limit }
  }
  return merged
}

export const PLGridForge = async () => ({
  config: async (config) => {
    config.provider = config.provider ?? {}
    const user = config.provider.plgrid ?? {}
    // Anything the user sets in opencode.json wins over the defaults above. `options`
    // and `models` are merged rather than replaced: a shallow spread would drop
    // baseURL when a user sets any option, and every other model when they
    // override one.
    config.provider.plgrid = {
      npm: "@ai-sdk/openai-compatible",
      name: "PLGrid Forge (Cyfronet)",
      ...user,
      options: { baseURL: BASE_URL, ...(user.options ?? {}) },
      models: mergeModels(MODELS, user.models ?? {}),
    }
  },

  auth: {
    provider: "plgrid",
    loader: async (getAuth) => {
      const auth = await getAuth()
      if (auth?.type === "api") return { apiKey: auth.key }
      return {}
    },
    methods: [
      {
        type: "api",
        label: "API Key (llmlab.plgrid.pl -> Grants -> Generate API Key)",
      },
    ],
  },
})
