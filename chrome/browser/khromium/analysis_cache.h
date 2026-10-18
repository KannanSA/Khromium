// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_KHROMIUM_ANALYSIS_CACHE_H_
#define CHROME_BROWSER_KHROMIUM_ANALYSIS_CACHE_H_

#include <map>
#include <optional>
#include <string>

#include "base/time/time.h"
#include "components/khromium/decision.h"

namespace khromium {

// One successful model result per registrable domain, kept for `ttl`.
class AnalysisCache {
 public:
  void LoadFromJson(const std::string& json, base::Time now, base::TimeDelta ttl);
  std::string ToJson() const;

  std::optional<AnalysisDecision> Lookup(const std::string& domain,
                                         base::Time now,
                                         base::TimeDelta ttl) const;
  void Store(const std::string& domain,
             const AnalysisDecision& decision,
             base::Time now);

 private:
  struct Entry {
    AnalysisDecision decision;
    base::Time stored;
  };
  std::map<std::string, Entry> entries_;
};

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_ANALYSIS_CACHE_H_
