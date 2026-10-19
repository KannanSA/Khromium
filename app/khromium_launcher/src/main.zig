// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See LICENSE.khromium at the repo root.
//
// Khromium desktop app. Windows and Intel macOS builds open a native window.
// This is not a browser build.

const builtin = @import("builtin");

pub fn main() u8 {
    if (comptime builtin.os.tag == .windows) return @import("windows.zig").run();
    if (comptime builtin.os.tag == .macos) return @import("macos.zig").run();
    // The host build is only a smoke test. It is not a published download.
    return @import("copy.zig").selfCheck();
}
