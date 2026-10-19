// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#include "components/khromium/decision.h"

#include <string>

#include "base/json/json_reader.h"
#include "base/strings/string_util.h"
#include "base/values.h"

namespace khromium {
namespace {

constexpr size_t kMaxSelectors = 8;
constexpr size_t kMaxSelectorLength = 200;
constexpr size_t kMaxReasonLength = 400;

std::string StripFence(std::string_view raw) {
  std::string text(base::TrimWhitespaceASCII(raw, base::TRIM_ALL));
  if (!base::StartsWith(text, "```", base::CompareCase::SENSITIVE)) {
    return text;
  }
  const size_t newline = text.find('\n');
  if (newline == std::string::npos) {
    return text;
  }
  text = text.substr(newline + 1);
  if (base::EndsWith(text, "```", base::CompareCase::SENSITIVE)) {
    text.resize(text.size() - 3);
  }
  return std::string(base::TrimWhitespaceASCII(text, base::TRIM_ALL));
}

bool StartsWithElement(std::string_view selector, std::string_view element) {
  if (!selector.starts_with(element)) {
    return false;
  }
  if (selector.size() == element.size()) {
    return true;
  }
  const char next = selector[element.size()];
  return next == ' ' || next == '>' || next == '+' || next == ',' ||
         next == '.' || next == '#' || next == ':' || next == '[';
}

// Selectors are applied with querySelectorAll in an isolated world. Keep the
// grammar to a specific CSS selector so a model reply cannot hide the whole
// document or smuggle a script.
bool SelectorIsSafe(std::string_view selector) {
  if (selector.empty() || selector.size() > kMaxSelectorLength) {
    return false;
  }
  bool specific = false;
  for (char c : selector) {
    const unsigned char uc = static_cast<unsigned char>(c);
    const bool ok = (uc >= 'a' && uc <= 'z') || (uc >= 'A' && uc <= 'Z') ||
                    (uc >= '0' && uc <= '9') || c == ' ' || c == '_' ||
                    c == '-' || c == '#' || c == '.' || c == ':' || c == '[' ||
                    c == ']' || c == '=' || c == '"' || c == '\'' || c == '^' ||
                    c == '$' || c == '*' || c == '~' || c == '|' || c == '>' ||
                    c == '+' || c == ',';
    if (!ok) {
      return false;
    }
    if (c == '#' || c == '.' || c == '[') {
      specific = true;
    }
  }
  if (!specific) {
    return false;
  }
  const std::string lower = base::ToLowerASCII(selector);
  if (lower.find("javascript") != std::string::npos ||
      lower.find("expression") != std::string::npos ||
      lower.find("url(") != std::string::npos) {
    return false;
  }
  std::string_view trimmed(lower);
  while (!trimmed.empty() && trimmed.front() == ' ') {
    trimmed.remove_prefix(1);
  }
  if (StartsWithElement(trimmed, "html") || StartsWithElement(trimmed, "body")) {
    return false;
  }
  return true;
}

std::optional<AnalysisDecision> FromDict(const base::DictValue& dict) {
  const std::optional<bool> block = dict.FindBool("block");
  const std::optional<bool> restore = dict.FindBool("restore_scroll");
  const std::string* reason = dict.FindString("reason");
  const base::ListValue* selectors = dict.FindList("selectors");
  if (!block || !restore || !reason || !selectors) {
    return std::nullopt;
  }
  if (selectors->size() > 32) {
    return std::nullopt;
  }

  AnalysisDecision decision;
  decision.block = *block;
  decision.restore_scroll = *restore;
  decision.reason = *reason;
  if (decision.reason.size() > kMaxReasonLength) {
    decision.reason.resize(kMaxReasonLength);
  }
  for (const base::Value& item : *selectors) {
    if (!item.is_string() || !SelectorIsSafe(item.GetString())) {
      continue;
    }
    if (decision.selectors.size() >= kMaxSelectors) {
      break;
    }
    decision.selectors.push_back(item.GetString());
  }
  // A block decision with no usable selector would hide nothing, or worse,
  // would invite the renderer to guess. Drop the block.
  if (decision.block && decision.selectors.empty()) {
    decision.block = false;
    decision.restore_scroll = false;
    decision.reason = "no safe selector";
  }
  return decision;
}

}  // namespace

std::optional<AnalysisDecision> ParseDecisionJson(std::string_view json) {
  const std::string stripped = StripFence(json);
  std::optional<base::DictValue> dict =
      base::JSONReader::ReadDict(stripped, base::JSON_PARSE_RFC);
  if (!dict) {
    return std::nullopt;
  }
  return FromDict(*dict);
}

std::optional<AnalysisDecision> ParseChatCompletionBody(std::string_view body) {
  std::optional<base::DictValue> root =
      base::JSONReader::ReadDict(body, base::JSON_PARSE_RFC);
  if (!root) {
    return ParseDecisionJson(body);
  }
  if (root->FindBool("block").has_value()) {
    return FromDict(*root);
  }
  const base::ListValue* choices = root->FindList("choices");
  if (!choices || choices->empty() || !(*choices)[0].is_dict()) {
    return std::nullopt;
  }
  const base::DictValue* message = (*choices)[0].GetDict().FindDict("message");
  if (!message) {
    return std::nullopt;
  }
  const std::string* content = message->FindString("content");
  if (!content) {
    return std::nullopt;
  }
  return ParseDecisionJson(*content);
}

}  // namespace khromium
