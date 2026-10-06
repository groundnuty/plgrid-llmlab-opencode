// PLGrid Forge (ACK Cyfronet) - unofficial opencode provider plugin.
//
// One file serves both OpenCode release lines, which have different plugin APIs:
//   1.x (1.18.5 or newer) - calls server(): the config and auth hooks below
//   2.x                   - calls setup(): registers the same provider, models
//                           and API-key login through V2 transforms
//
// Drop this file into one of:
//   <project>/.opencode/plugins/      - this project only
//   ~/.config/opencode/plugins/       - every project on this machine
// or publish it as an npm package / git repo and reference it from the
// "plugin" array in opencode.json, so colleagues can install it and log in
// with their own PLGrid grant key.
//
// After installing, authenticate once with:
//   opencode providers login -p plgrid   (1.x - stored in ~/.local/share/opencode/auth.json)
//   opencode auth login plgrid           (2.x - stored in ~/.local/share/opencode/opencode.db)
// No key ever needs to appear in a config file or an environment variable.
//
// Model metadata below is measured against the live gateway, not guessed:
//   tool_call       - the gateway's function_calling_supported field, confirmed
//                     by a structured tool call
//   attachment      - vision-language model (Qwen3-VL)
//   reasoning       - the model returns chain of thought in the message's
//                     "reasoning" field; interleaved.field is the name OpenCode
//                     uses to send it back on later turns (the gateway accepts
//                     both "reasoning" and "reasoning_content")
//   limit.context   - from the server's own max_model_len error messages
//   limit.output    - kept well under context; opencode sends this verbatim
//                     as max_tokens, and the gateway enforces
//                     input + max_tokens <= context
//
// Every active chat model is listed, whichever grant can reach it. Access is per
// grant, and the catalog's "accessible" field is answered for the caller's account,
// so this list is not filtered by it: a model your key's grant cannot use answers
// "not available for grant". The embedding model (Qwen/Qwen3-Embedding-0.6B) is
// absent because OpenCode cannot use an embedding model as a chat model.

const BASE_URL = "https://llmlab.plgrid.pl/api/v1"
const PROVIDER_ID = "plgrid"
const PROVIDER_NAME = "PLGrid Forge (Cyfronet)"
const KEY_LABEL = "API Key (llmlab.plgrid.pl -> Grants -> Generate API Key)"

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
  },
  "feyninc/sqrl-9b": {
    "name": "sqrl 9B",
    "tool_call": false
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
      name: PROVIDER_NAME,
      ...user,
      options: { baseURL: BASE_URL, ...(user.options ?? {}) },
      models: mergeModels(MODELS, user.models ?? {}),
    }
  },

  auth: {
    provider: PROVIDER_ID,
    loader: async (getAuth) => {
      const auth = await getAuth()
      if (auth?.type === "api") return { apiKey: auth.key }
      return {}
    },
    methods: [
      {
        type: "api",
        label: KEY_LABEL,
      },
    ],
  },
})

// OpenCode 2.x has neither hook. The key method makes `opencode auth login plgrid`
// work, and the provider stays hidden until a key is stored. interleaved.field is
// called compatibility.reasoningField in 2.x, and a model's input must be listed
// explicitly: 2.x assumes text and image unless told otherwise.
const setup = async (ctx) => {
  await ctx.integration.transform((integrations) => {
    integrations.update(PROVIDER_ID, (integration) => {
      integration.name = PROVIDER_NAME
    })
    integrations.method.update({ integrationID: PROVIDER_ID, method: { type: "key", label: KEY_LABEL } })
  })
  await ctx.provider.transform((providers) => {
    providers.update(PROVIDER_ID, (provider) => {
      provider.name = PROVIDER_NAME
      provider.package = "@opencode/ai/providers/openai-compatible"
      provider.settings = { baseURL: BASE_URL, ...provider.settings }
    })
    for (const [id, model] of Object.entries(MODELS)) {
      providers.models.update(PROVIDER_ID, id, (draft) => {
        draft.name = model.name
        draft.capabilities = {
          tools: model.tool_call,
          input: model.attachment ? ["text", "image"] : ["text"],
          output: ["text"],
        }
        if (model.limit) draft.limit = { ...draft.limit, ...model.limit }
        if (model.interleaved) draft.compatibility = { ...draft.compatibility, reasoningField: model.interleaved.field }
      })
    }
  })
}

// 1.x calls server and 2.x calls setup; 2.x rejects a plugin without this default
// export. PLGridForge stays a named export as well, and 1.x still runs the plugin once.
export default { id: PROVIDER_ID, server: PLGridForge, setup }
