// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef COMPONENTS_KHROMIUM_SYSTEM_PROMPT_H_
#define COMPONENTS_KHROMIUM_SYSTEM_PROMPT_H_

#include <string_view>

namespace khromium {

// Keep this text identical to
// app/khromium_classifier/khromium_classifier/prompt.py.
std::string_view GetSystemPrompt();

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_SYSTEM_PROMPT_H_
