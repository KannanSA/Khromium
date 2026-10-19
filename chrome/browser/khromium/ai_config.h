// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef CHROME_BROWSER_KHROMIUM_AI_CONFIG_H_
#define CHROME_BROWSER_KHROMIUM_AI_CONFIG_H_

#include <string>

#include "base/files/file_path.h"

namespace khromium {

enum class AiProvider { kOpenAi, kGrok };

struct AiConfig {
  AiProvider provider = AiProvider::kOpenAi;
  std::string model;
  // Provider key. Set only when KHROMIUM_ALLOW_BYO_KEY=1 (dev-only, off by
  // default). Never log this field. Paid AI does not put a provider key here.
  std::string api_key;
  std::string endpoint;
  // License token sent to the Khromium proxy as X-Khromium-License.
  // This is not the provider API key.
  std::string license_key;
  // Paid path. False only for the dev-only bring-your-own-key override.
  bool use_proxy = true;

  bool has_key() const { return !api_key.empty(); }
  bool can_call() const {
    if (endpoint.empty()) {
      return false;
    }
    if (use_proxy) {
      return !license_key.empty();
    }
    return !api_key.empty();
  }
};

// Reads provider and model from <profile>/khromium/ai_config.json when that
// file exists. The paid path ignores provider keys in the file and in
// KHROMIUM_OPENAI_API_KEY / KHROMIUM_XAI_API_KEY. It calls
// KHROMIUM_AI_PROXY_URL (default http://127.0.0.1:8766/v1/chat/completions).
// KHROMIUM_ALLOW_BYO_KEY=1 restores the direct provider call for development.
// The raw file bytes are discarded after parse and are never logged.
AiConfig LoadAiConfig(const base::FilePath& config_path,
                      const std::string& provider_pref);

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_AI_CONFIG_H_
