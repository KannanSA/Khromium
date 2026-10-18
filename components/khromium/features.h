// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef COMPONENTS_KHROMIUM_FEATURES_H_
#define COMPONENTS_KHROMIUM_FEATURES_H_

#include "base/feature_list.h"

namespace khromium {

// Opt-in switch for the paid Khromium Shield classifier.
// Disabled by default. Enable with --enable-features=KhromiumAiAdShield.
// The profile pref khromium.ai_shield_enabled can turn it back off.
// A valid paid license is still required; the flag alone does not unlock it.
BASE_DECLARE_FEATURE(kKhromiumAiAdShield);

namespace prefs {

inline constexpr char kAiShieldEnabled[] = "khromium.ai_shield_enabled";
inline constexpr char kProvider[] = "khromium.provider";
inline constexpr char kCacheTtlHours[] = "khromium.cache_ttl_hours";

}  // namespace prefs

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_FEATURES_H_
