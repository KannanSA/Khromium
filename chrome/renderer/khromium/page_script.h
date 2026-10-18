// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_RENDERER_KHROMIUM_PAGE_SCRIPT_H_
#define CHROME_RENDERER_KHROMIUM_PAGE_SCRIPT_H_

#include <string>
#include <vector>

namespace khromium {

// Isolated-world scan. Returns a JSON snippet, or empty when nothing looks
// like an anti-adblock wall or an obfuscated ad container.
std::string HeuristicScanScript();

// Removes the selectors the model returned and, when asked, clears
// overflow:hidden on html and body so the page can scroll again.
std::string CleanupScript(const std::vector<std::string>& selectors,
                          bool restore_scroll);

}  // namespace khromium

#endif  // CHROME_RENDERER_KHROMIUM_PAGE_SCRIPT_H_
