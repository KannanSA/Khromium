// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef COMPONENTS_KHROMIUM_DECISION_H_
#define COMPONENTS_KHROMIUM_DECISION_H_

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace khromium {

struct AnalysisDecision {
  bool block = false;
  std::vector<std::string> selectors;
  bool restore_scroll = false;
  std::string reason;
  bool from_cache = false;
};

// Parses the strict JSON object the system prompt demands. Strips a single
// ```json fence if the model adds one. Returns nullopt when required fields
// are missing. Unsafe selectors are dropped; a block with none left becomes
// block=false.
std::optional<AnalysisDecision> ParseDecisionJson(std::string_view json);

// Accepts either the decision object or a chat-completions response and
// pulls choices[0].message.content through ParseDecisionJson.
std::optional<AnalysisDecision> ParseChatCompletionBody(std::string_view body);

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_DECISION_H_
