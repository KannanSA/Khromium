// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See LICENSE.khromium at the repo root.
//
// Text shown by the Khromium desktop app. The only address it opens is site_url.

const std = @import("std");

pub const title = "Khromium";
pub const body = "A one-time browser purchase includes 30 days of AI ad-block. Monthly AI is twice the API cost, and Khromium provides the model key.";
pub const hint = "Press Enter to open http://127.0.0.1:8787";
pub const button_label = "Open download site";
pub const site_url = "http://127.0.0.1:8787";
pub const open_failed = "Khromium could not open http://127.0.0.1:8787. Start the download site, then try again.";

/// The desktop app never takes a URL from the user. This guard is what the
/// self-check and the open path both use.
pub fn isSiteUrl(url: []const u8) bool {
    return std.mem.eql(u8, url, site_url);
}

pub fn selfCheck() u8 {
    const required = [_][]const u8{
        "Khromium",
        "30 days",
        "twice the API cost",
        "model key",
        site_url,
    };
    const blob = title ++ "\n" ++ body ++ "\n" ++ hint ++ "\n" ++ button_label;
    for (required) |phrase| {
        if (std.mem.indexOf(u8, blob, phrase) == null) return 1;
    }
    if (!isSiteUrl(site_url)) return 1;
    const rejected = [_][]const u8{
        "https://example.com",
        "http://127.0.0.1.evil.example",
        "http://127.0.0.1:8787/../secret",
        "http://localhost:8787",
        "http://127.0.0.1:8788",
        "http://127.0.0.1:8787/",
        "http://127.0.0.1",
        "",
    };
    for (rejected) |url| {
        if (isSiteUrl(url)) return 1;
    }

    const stdout = std.io.getStdOut().writer();
    stdout.print("{s}\n{s}\n{s}\n{s}\n", .{ title, body, hint, site_url }) catch return 1;
    return 0;
}
