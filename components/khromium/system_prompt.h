// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef COMPONENTS_KHROMIUM_SYSTEM_PROMPT_H_
#define COMPONENTS_KHROMIUM_SYSTEM_PROMPT_H_

#include <string_view>

namespace khromium {

// Keep this text identical to
// app/khromium_classifier/khromium_classifier/prompt.py.
std::string_view GetSystemPrompt();

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_SYSTEM_PROMPT_H_
