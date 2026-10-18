// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef COMPONENTS_KHROMIUM_SCRIPT_PATTERNS_H_
#define COMPONENTS_KHROMIUM_SCRIPT_PATTERNS_H_

#include <string_view>

namespace khromium {

// Substrings matched against script URLs. Kept narrow on purpose so ordinary
// ad SDKs are not blocked here; those are a subresource_filter concern.
inline constexpr std::string_view kAntiAdblockScriptMarkers[] = {
    "fuckadblock",     "blockadblock", "antiadblock",
    "adblock-detector", "adblockdetect", "adbdetect",
};

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_SCRIPT_PATTERNS_H_
