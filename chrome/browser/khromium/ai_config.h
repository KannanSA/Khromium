// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_KHROMIUM_AI_CONFIG_H_
#define CHROME_BROWSER_KHROMIUM_AI_CONFIG_H_

#include <string>

#include "base/files/file_path.h"

namespace khromium {

enum class AiProvider { kOpenAi, kGrok };

struct AiConfig {
  AiProvider provider = AiProvider::kOpenAi;
  std::string model;
  // Present only in memory. Never log this field.
  std::string api_key;
  std::string endpoint;
  bool has_key() const { return !api_key.empty(); }
};

// Reads <profile>/khromium/ai_config.json if it exists. Environment variables
// KHROMIUM_OPENAI_API_KEY and KHROMIUM_XAI_API_KEY override any key in the
// file. The raw file bytes are discarded after parse and are never logged.
AiConfig LoadAiConfig(const base::FilePath& config_path,
                      const std::string& provider_pref);

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_AI_CONFIG_H_
