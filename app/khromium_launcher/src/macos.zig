// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See LICENSE.khromium at the repo root.
//
// Intel macOS window. The binary links AppKit, Foundation, and libobjc.
// Cross-compiling from Linux uses install-name stubs because the Mac SDK is
// not on that machine. On a Mac, dyld loads the real frameworks.
// If those classes are missing at runtime, the same binary shows an osascript
// dialog and opens the local site with /usr/bin/open.

const std = @import("std");
const copy = @import("copy.zig");

const id = ?*anyopaque;
const SEL = ?*anyopaque;

const NSPoint = extern struct { x: f64, y: f64 };
const NSSize = extern struct { width: f64, height: f64 };
const NSRect = extern struct { origin: NSPoint, size: NSSize };

extern "c" fn objc_getClass(name: [*:0]const u8) id;
extern "c" fn sel_registerName(name: [*:0]const u8) SEL;
extern "c" fn objc_msgSend(obj: id, sel: SEL) callconv(.C) id;
extern "c" fn objc_allocateClassPair(super: id, name: [*:0]const u8, extra: usize) id;
extern "c" fn objc_registerClassPair(cls: id) void;
extern "c" fn class_addMethod(cls: id, name: SEL, imp: *const anyopaque, types: [*:0]const u8) u8;

fn castMsg(comptime F: type) F {
    return @ptrFromInt(@intFromPtr(&objc_msgSend));
}

fn call0(comptime R: type, obj: id, name: [*:0]const u8) R {
    const F = *const fn (id, SEL) callconv(.C) R;
    return castMsg(F)(obj, sel_registerName(name));
}

fn call1(comptime R: type, comptime A: type, obj: id, name: [*:0]const u8, arg: A) R {
    const F = *const fn (id, SEL, A) callconv(.C) R;
    return castMsg(F)(obj, sel_registerName(name), arg);
}

fn call4f(obj: id, name: [*:0]const u8, a: f64, b: f64, c: f64, d: f64) id {
    const F = *const fn (id, SEL, f64, f64, f64, f64) callconv(.C) id;
    return castMsg(F)(obj, sel_registerName(name), a, b, c, d);
}

fn callFrame(comptime R: type, obj: id, name: [*:0]const u8, frame: NSRect) R {
    const F = *const fn (id, SEL, NSRect) callconv(.C) R;
    return castMsg(F)(obj, sel_registerName(name), frame);
}

fn initWindow(obj: id, frame: NSRect, style: c_ulong, backing: c_ulong, defer_window: u8) id {
    const F = *const fn (id, SEL, NSRect, c_ulong, c_ulong, u8) callconv(.C) id;
    return castMsg(F)(obj, sel_registerName("initWithContentRect:styleMask:backing:defer:"), frame, style, backing, defer_window);
}

fn ns(text: [*:0]const u8) id {
    const allocated = call0(id, objc_getClass("NSString"), "alloc");
    return call1(id, [*:0]const u8, allocated, "initWithUTF8String:", text);
}

fn color(r: f64, g: f64, b: f64, a: f64) id {
    return call4f(objc_getClass("NSColor"), "colorWithCalibratedRed:green:blue:alpha:", r, g, b, a);
}

fn makeRect(x: f64, y: f64, w: f64, h: f64) NSRect {
    return .{
        .origin = .{ .x = x, .y = y },
        .size = .{ .width = w, .height = h },
    };
}

fn openLocalSite() bool {
    if (!copy.isSiteUrl(copy.site_url)) return false;
    const argv = [_][]const u8{ "/usr/bin/open", copy.site_url };
    var child = std.process.Child.init(&argv, std.heap.page_allocator);
    child.stdout_behavior = .Ignore;
    child.stderr_behavior = .Ignore;
    const term = child.spawnAndWait() catch return false;
    return switch (term) {
        .Exited => |code| code == 0,
        else => false,
    };
}

fn showOpenFailed() void {
    const alert = call0(id, call0(id, objc_getClass("NSAlert"), "alloc"), "init");
    if (alert == null) return;
    _ = call1(void, id, alert, "setMessageText:", ns(copy.title));
    _ = call1(void, id, alert, "setInformativeText:", ns(copy.open_failed));
    _ = call0(c_long, alert, "runModal");
}

fn openClicked(_: id, _: SEL, _: id) callconv(.C) void {
    if (!openLocalSite()) showOpenFailed();
}

fn shouldTerminate(_: id, _: SEL, _: id) callconv(.C) i8 {
    return 1;
}

fn classesReady() bool {
    const names = [_][*:0]const u8{
        "NSObject",
        "NSApplication",
        "NSWindow",
        "NSString",
        "NSColor",
        "NSFont",
        "NSTextField",
        "NSButton",
        "NSImage",
        "NSImageView",
        "NSAlert",
        "NSAutoreleasePool",
    };
    for (names) |name| {
        if (objc_getClass(name) == null) return false;
    }
    return true;
}

fn logoPath(buf: *[1024]u8) ?[:0]const u8 {
    var exe_buf: [4096]u8 = .{0} ** 4096;
    var size: u32 = exe_buf.len;
    if (std.c._NSGetExecutablePath(@ptrCast(&exe_buf), &size) != 0) return null;
    const exe = std.mem.sliceTo(exe_buf[0..], 0);
    const slash = std.mem.lastIndexOfScalar(u8, exe, '/') orelse return null;
    const dir = exe[0..slash];
    const marker = "/Contents/MacOS";
    if (!std.mem.endsWith(u8, dir, marker)) return null;
    const prefix = dir[0 .. dir.len - marker.len];
    const suffix = "/Contents/Resources/AppIcon.png";
    if (prefix.len + suffix.len + 1 > buf.len) return null;
    @memcpy(buf[0..prefix.len], prefix);
    @memcpy(buf[prefix.len..][0..suffix.len], suffix);
    const len = prefix.len + suffix.len;
    buf[len] = 0;
    const path = buf[0..len :0];
    std.posix.access(path, std.posix.F_OK) catch return null;
    return path;
}

fn addLabel(parent: id, frame: NSRect, text: [*:0]const u8, size: f64, bold: bool, r: f64, g: f64, b: f64, wraps: bool) void {
    const field = callFrame(id, call0(id, objc_getClass("NSTextField"), "alloc"), "initWithFrame:", frame);
    if (field == null) return;
    _ = call1(void, id, field, "setStringValue:", ns(text));
    _ = call1(void, u8, field, "setBezeled:", 0);
    _ = call1(void, u8, field, "setDrawsBackground:", 0);
    _ = call1(void, u8, field, "setEditable:", 0);
    _ = call1(void, u8, field, "setSelectable:", 0);
    _ = call1(void, u8, field, "setBordered:", 0);
    const font = if (bold)
        call1(id, f64, objc_getClass("NSFont"), "boldSystemFontOfSize:", size)
    else
        call1(id, f64, objc_getClass("NSFont"), "systemFontOfSize:", size);
    _ = call1(void, id, field, "setFont:", font);
    _ = call1(void, id, field, "setTextColor:", color(r, g, b, 1));
    if (wraps) {
        const cell = call0(id, field, "cell");
        if (cell != null) _ = call1(void, u8, cell, "setWraps:", 1);
    }
    _ = call1(void, id, parent, "addSubview:", field);
}

fn appKitWindow() bool {
    if (!classesReady()) return false;
    const pool = call0(id, call0(id, objc_getClass("NSAutoreleasePool"), "alloc"), "init");
    _ = pool;

    const app = call0(id, objc_getClass("NSApplication"), "sharedApplication");
    if (app == null) return false;
    _ = call1(void, c_long, app, "setActivationPolicy:", 0);

    const controller_class = objc_allocateClassPair(objc_getClass("NSObject"), "KhromiumController", 0) orelse return false;
    if (class_addMethod(controller_class, sel_registerName("openSite:"), @ptrCast(&openClicked), "v@:@") == 0) return false;
    if (class_addMethod(controller_class, sel_registerName("applicationShouldTerminateAfterLastWindowClosed:"), @ptrCast(&shouldTerminate), "c@:@") == 0) return false;
    objc_registerClassPair(controller_class);
    const controller = call0(id, call0(id, controller_class, "alloc"), "init");
    if (controller == null) return false;
    _ = call1(void, id, app, "setDelegate:", controller);

    const window = initWindow(
        call0(id, objc_getClass("NSWindow"), "alloc"),
        makeRect(0, 0, 740, 440),
        1 | 2 | 4,
        2,
        0,
    );
    if (window == null) return false;
    _ = call1(void, id, window, "setTitle:", ns(copy.title));
    _ = call1(void, id, window, "setBackgroundColor:", color(244.0 / 255.0, 248.0 / 255.0, 251.0 / 255.0, 1));
    _ = call1(void, u8, window, "setReleasedWhenClosed:", 0);
    call0(void, window, "center");

    const content = call0(id, window, "contentView");
    if (content == null) return false;

    var path_buf: [1024]u8 = undefined;
    if (logoPath(&path_buf)) |path| {
        const image = call1(id, id, call0(id, objc_getClass("NSImage"), "alloc"), "initWithContentsOfFile:", ns(path));
        if (image != null) {
            const view = callFrame(id, call0(id, objc_getClass("NSImageView"), "alloc"), "initWithFrame:", makeRect(36, 200, 200, 200));
            if (view != null) {
                _ = call1(void, id, view, "setImage:", image);
                _ = call1(void, c_ulong, view, "setImageScaling:", 3);
                _ = call1(void, id, content, "addSubview:", view);
            }
        }
    }

    const ink_r = 8.0 / 255.0;
    const ink_g = 36.0 / 255.0;
    const ink_b = 63.0 / 255.0;
    addLabel(content, makeRect(264, 356, 440, 42), copy.title, 30, true, ink_r, ink_g, ink_b, false);
    addLabel(content, makeRect(264, 214, 440, 130), copy.body, 16, false, ink_r, ink_g, ink_b, true);
    addLabel(content, makeRect(264, 78, 440, 24), copy.hint, 13, false, 26.0 / 255.0, 78.0 / 255.0, 104.0 / 255.0, false);

    const button = callFrame(id, call0(id, objc_getClass("NSButton"), "alloc"), "initWithFrame:", makeRect(264, 32, 240, 36));
    if (button == null) return false;
    _ = call1(void, id, button, "setTitle:", ns(copy.button_label));
    _ = call1(void, c_ulong, button, "setBezelStyle:", 1);
    _ = call1(void, id, button, "setTarget:", controller);
    _ = call1(void, SEL, button, "setAction:", sel_registerName("openSite:"));
    _ = call1(void, id, button, "setKeyEquivalent:", ns("\r"));
    _ = call1(void, id, content, "addSubview:", button);
    const cell = call0(id, button, "cell");
    if (cell != null) _ = call1(void, id, window, "setDefaultButtonCell:", cell);

    _ = call1(void, id, window, "makeKeyAndOrderFront:", null);
    _ = call1(void, u8, app, "activateIgnoringOtherApps:", 1);
    call0(void, app, "run");
    return true;
}

fn osascriptFallback() u8 {
    const script = "display dialog \"Khromium\n\n" ++ copy.body ++ "\n\n" ++ copy.hint ++
        "\" buttons {\"Quit\", \"Open download site\"} default button \"Open download site\" with title \"Khromium\"";
    const argv = [_][]const u8{ "/usr/bin/osascript", "-e", script };
    var child = std.process.Child.init(&argv, std.heap.page_allocator);
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Ignore;
    child.spawn() catch return 1;
    const stdout = child.stdout orelse return 1;
    const out = stdout.readToEndAlloc(std.heap.page_allocator, 8192) catch return 1;
    _ = child.wait() catch return 1;
    if (std.mem.indexOf(u8, out, "Open download site") != null) {
        if (!openLocalSite()) return 1;
    }
    return 0;
}

pub fn run() u8 {
    if (appKitWindow()) return 0;
    return osascriptFallback();
}
