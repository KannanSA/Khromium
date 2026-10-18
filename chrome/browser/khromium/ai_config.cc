// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#include "chrome/browser/khromium/ai_config.h"

#include <optional>

#include "base/environment.h"
#include "base/files/file_util.h"
#include "base/json/json_reader.h"
#include "base/strings/string_util.h"

namespace khromium {
namespace {

constexpr char kOpenAiEndpoint[] = "https://api.openai.com/v1/chat/completions";
constexpr char kGrokEndpoint[] = "https://api.x.ai/v1/chat/completions";
constexpr char kOpenAiModel[] = "gpt-4o-mini";
constexpr char kGrokModel[] = "grok-3-mini";

std::optional<std::string> EnvVar(const char* name) {
  std::unique_ptr<base::Environment> env = base::Environment::Create();
  std::optional<std::string> value = env->GetVar(name);
  if (!value || value->empty()) {
    return std::nullopt;
  }
  return value;
}

}  // namespace

AiConfig LoadAiConfig(const base::FilePath& config_path,
                      const std::string& provider_pref) {
  AiConfig config;
  std::string provider = base::ToLowerASCII(provider_pref);

  std::string raw;
  base::DictValue file;
  if (base::ReadFileToStringWithMaxSize(config_path, &raw, 64 * 1024)) {
    if (std::optional<base::DictValue> parsed =
            base::JSONReader::ReadDict(raw, base::JSON_PARSE_RFC)) {
      file = std::move(*parsed);
    }
  }
  // Drop the raw document so a key in the file is not kept twice.
  raw.clear();
  raw.shrink_to_fit();

  if (const std::string* from_file = file.FindString("provider")) {
    provider = base::ToLowerASCII(*from_file);
  }
  config.provider =
      provider == "grok" || provider == "xai" ? AiProvider::kGrok
                                              : AiProvider::kOpenAi;
  if (config.provider == AiProvider::kGrok) {
    config.model = kGrokModel;
    config.endpoint = kGrokEndpoint;
  } else {
    config.model = kOpenAiModel;
    config.endpoint = kOpenAiEndpoint;
  }
  if (const std::string* model = file.FindString("model");
      model && !model->empty()) {
    config.model = *model;
  }

  if (config.provider == AiProvider::kGrok) {
    if (std::optional<std::string> env = EnvVar("KHROMIUM_XAI_API_KEY")) {
      config.api_key = *env;
    } else if (const std::string* key = file.FindString("xai_api_key")) {
      config.api_key = *key;
    }
  } else {
    if (std::optional<std::string> env = EnvVar("KHROMIUM_OPENAI_API_KEY")) {
      config.api_key = *env;
    } else if (const std::string* key = file.FindString("openai_api_key")) {
      config.api_key = *key;
    }
  }
  return config;
}

}  // namespace khromium
