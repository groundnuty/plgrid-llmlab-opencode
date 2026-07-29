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
// Model metadata below was measured against the live gateway, not guessed:
//   limit.context   - from the server's own max_model_len error messages
//   tool_call       - from PLGrid's function_calling_supported field
//   limit.output    - kept well under context; opencode sends this verbatim
//                     as max_tokens, and the gateway enforces
//                     input + max_tokens <= context

const BASE_URL = "https://llmlab.plgrid.pl/api/v1"

const MODELS = {
  "zai-org/GLM-5.2-FP8": {
    "name": "GLM-5.2 FP8",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning_content"
    },
    "limit": {
      "context": 393216,
      "output": 32768
    }
  },
  "zai-org/GLM-4.7-Flash": {
    "name": "GLM-4.7 Flash",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning_content"
    },
    "limit": {
      "context": 202752,
      "output": 32768
    }
  },
  "Qwen/Qwen3-Coder-30B-A3B-Instruct": {
    "name": "Qwen3 Coder 30B A3B",
    "tool_call": true,
    "limit": {
      "context": 249600,
      "output": 32768
    }
  },
  "Qwen/Qwen3.6-27B": {
    "name": "Qwen3.6 27B",
    "tool_call": true,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning_content"
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
      "field": "reasoning_content"
    },
    "limit": {
      "context": 262144,
      "output": 32768
    }
  },
  "Qwen/QwQ-32B": {
    "name": "QwQ 32B",
    "tool_call": false,
    "reasoning": true,
    "interleaved": {
      "field": "reasoning_content"
    },
    "limit": {
      "context": 40960,
      "output": 8192
    }
  },
  "google/gemma-4-31B": {
    "name": "Gemma 4 31B",
    "tool_call": true,
    "limit": {
      "context": 262144,
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
  },
  "Qwen/Qwen3.5-397B-A17B-FP8": {
    "name": "Qwen3.5 397B A17B FP8 (grant access required)",
    "tool_call": true
  },
  "Qwen/Qwen3.5-122B-A10B": {
    "name": "Qwen3.5 122B A10B (grant access required)",
    "tool_call": true
  },
  "meta-llama/Llama-3.3-70B-Instruct": {
    "name": "Llama 3.3 70B Instruct (currently inactive)",
    "tool_call": false,
    "limit": {
      "context": 131072,
      "output": 16384
    }
  }
}

export const PLGridForge = async () => ({
  config: async (config) => {
    config.provider = config.provider ?? {}
    config.provider.plgrid = {
      npm: "@ai-sdk/openai-compatible",
      name: "PLGrid Forge (Cyfronet)",
      options: { baseURL: BASE_URL },
      models: MODELS,
      // anything the user sets in opencode.json wins over the defaults above
      ...(config.provider.plgrid ?? {}),
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
