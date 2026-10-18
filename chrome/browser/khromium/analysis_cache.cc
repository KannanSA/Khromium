// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#include "chrome/browser/khromium/analysis_cache.h"

#include "base/json/json_reader.h"
#include "base/json/json_writer.h"
#include "base/values.h"

namespace khromium {
namespace {

base::Time FromUnix(double seconds) {
  return base::Time::FromSecondsSinceUnixEpoch(seconds);
}

}  // namespace

void AnalysisCache::LoadFromJson(const std::string& json,
                                 base::Time now,
                                 base::TimeDelta ttl) {
  entries_.clear();
  std::optional<base::DictValue> root =
      base::JSONReader::ReadDict(json, base::JSON_PARSE_RFC);
  if (!root) {
    return;
  }
  const base::DictValue* entries = root->FindDict("entries");
  if (!entries) {
    return;
  }
  for (const auto [domain, value] : *entries) {
    if (!value.is_dict()) {
      continue;
    }
    const base::DictValue& dict = value.GetDict();
    const std::optional<double> stored = dict.FindDouble("stored_at");
    const std::optional<bool> block = dict.FindBool("block");
    const std::optional<bool> restore = dict.FindBool("restore_scroll");
    const std::string* reason = dict.FindString("reason");
    const base::ListValue* selectors = dict.FindList("selectors");
    if (!stored || !block || !restore || !reason || !selectors) {
      continue;
    }
    Entry entry;
    entry.stored = FromUnix(*stored);
    if (now - entry.stored > ttl) {
      continue;
    }
    entry.decision.block = *block;
    entry.decision.restore_scroll = *restore;
    entry.decision.reason = *reason;
    entry.decision.from_cache = true;
    for (const base::Value& item : *selectors) {
      if (item.is_string()) {
        entry.decision.selectors.push_back(item.GetString());
      }
    }
    entries_.emplace(std::string(domain), std::move(entry));
  }
}

std::string AnalysisCache::ToJson() const {
  base::DictValue entries;
  for (const auto& [domain, entry] : entries_) {
    base::DictValue dict;
    dict.Set("stored_at", entry.stored.InSecondsFSinceUnixEpoch());
    dict.Set("block", entry.decision.block);
    dict.Set("restore_scroll", entry.decision.restore_scroll);
    dict.Set("reason", entry.decision.reason);
    base::ListValue selectors;
    for (const std::string& selector : entry.decision.selectors) {
      selectors.Append(selector);
    }
    dict.Set("selectors", std::move(selectors));
    entries.Set(domain, std::move(dict));
  }
  base::DictValue root;
  root.Set("entries", std::move(entries));
  return base::WriteJson(root).value_or(std::string());
}

std::optional<AnalysisDecision> AnalysisCache::Lookup(
    const std::string& domain,
    base::Time now,
    base::TimeDelta ttl) const {
  const auto it = entries_.find(domain);
  if (it == entries_.end()) {
    return std::nullopt;
  }
  if (now - it->second.stored > ttl) {
    return std::nullopt;
  }
  return it->second.decision;
}

void AnalysisCache::Store(const std::string& domain,
                          const AnalysisDecision& decision,
                          base::Time now) {
  Entry entry;
  entry.decision = decision;
  entry.decision.from_cache = true;
  entry.stored = now;
  entries_[domain] = std::move(entry);
}

}  // namespace khromium
