// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See LICENSE.khromium at the repo root.
//
// Win32 window for the Khromium desktop app. The executable is built with
// subsystem WINDOWS, so double-clicking it does not open a console.

const std = @import("std");
const win = std.os.windows;
const copy = @import("copy.zig");

const button_id: usize = 1001;

const WM_DESTROY: u32 = 0x0002;
const WM_SIZE: u32 = 0x0005;
const WM_PAINT: u32 = 0x000F;
const WM_CLOSE: u32 = 0x0010;
const WM_KEYDOWN: u32 = 0x0100;
const WM_COMMAND: u32 = 0x0111;
const WM_CREATE: u32 = 0x0001;
const VK_RETURN: usize = 0x0D;
const WS_CLIPCHILDREN: u32 = 0x02000000;
const WS_CAPTION: u32 = 0x00C00000;
const WS_SYSMENU: u32 = 0x00080000;
const WS_MINIMIZEBOX: u32 = 0x00020000;
const WS_CHILD: u32 = 0x40000000;
const WS_VISIBLE: u32 = 0x10000000;
const WS_TABSTOP: u32 = 0x00010000;
const BS_DEFPUSHBUTTON: u32 = 0x00000001;
const CS_HREDRAW: u32 = 0x0002;
const CS_VREDRAW: u32 = 0x0001;
const SW_SHOW: c_int = 5;
const SW_SHOWNORMAL: c_int = 1;
const IMAGE_ICON: u32 = 1;
const DI_NORMAL: u32 = 3;
const DT_WORDBREAK: u32 = 0x00000010;
const DT_NOPREFIX: u32 = 0x00000800;
const TRANSPARENT: c_int = 1;
const LOGPIXELSX: c_int = 88;
const NULL_PEN: c_int = 8;
const FW_NORMAL: c_int = 400;
const FW_BOLD: c_int = 700;

const WNDCLASSEXW = extern struct {
    cbSize: win.UINT,
    style: win.UINT,
    lpfnWndProc: *const fn (win.HWND, win.UINT, win.WPARAM, win.LPARAM) callconv(.winapi) win.LRESULT,
    cbClsExtra: c_int,
    cbWndExtra: c_int,
    hInstance: win.HINSTANCE,
    hIcon: ?win.HICON,
    hCursor: ?win.HCURSOR,
    hbrBackground: ?win.HBRUSH,
    lpszMenuName: ?win.LPCWSTR,
    lpszClassName: win.LPCWSTR,
    hIconSm: ?win.HICON,
};

const MSG = extern struct {
    hwnd: ?win.HWND,
    message: win.UINT,
    wParam: win.WPARAM,
    lParam: win.LPARAM,
    time: win.DWORD,
    pt: win.POINT,
    lPrivate: win.DWORD,
};

const PAINTSTRUCT = extern struct {
    hdc: win.HDC,
    fErase: win.BOOL,
    rcPaint: win.RECT,
    fRestore: win.BOOL,
    fIncUpdate: win.BOOL,
    rgbReserved: [32]u8,
};

extern "kernel32" fn GetModuleHandleW(name: ?win.LPCWSTR) callconv(.winapi) ?win.HMODULE;
extern "user32" fn RegisterClassExW(wc: *const WNDCLASSEXW) callconv(.winapi) u16;
extern "user32" fn CreateWindowExW(
    ex_style: win.DWORD,
    class_name: win.LPCWSTR,
    window_name: win.LPCWSTR,
    style: win.DWORD,
    x: c_int,
    y: c_int,
    width: c_int,
    height: c_int,
    parent: ?win.HWND,
    menu: ?win.HMENU,
    instance: win.HINSTANCE,
    param: ?*anyopaque,
) callconv(.winapi) ?win.HWND;
extern "user32" fn ShowWindow(hwnd: win.HWND, cmd: c_int) callconv(.winapi) win.BOOL;
extern "user32" fn UpdateWindow(hwnd: win.HWND) callconv(.winapi) win.BOOL;
extern "user32" fn GetMessageW(msg: *MSG, hwnd: ?win.HWND, min: u32, max: u32) callconv(.winapi) win.BOOL;
extern "user32" fn TranslateMessage(msg: *const MSG) callconv(.winapi) win.BOOL;
extern "user32" fn DispatchMessageW(msg: *const MSG) callconv(.winapi) isize;
extern "user32" fn DefWindowProcW(hwnd: win.HWND, msg: win.UINT, wparam: win.WPARAM, lparam: win.LPARAM) callconv(.winapi) win.LRESULT;
extern "user32" fn PostQuitMessage(code: c_int) callconv(.winapi) void;
extern "user32" fn BeginPaint(hwnd: win.HWND, paint: *PAINTSTRUCT) callconv(.winapi) ?win.HDC;
extern "user32" fn EndPaint(hwnd: win.HWND, paint: *const PAINTSTRUCT) callconv(.winapi) win.BOOL;
extern "user32" fn FillRect(hdc: win.HDC, rect: *const win.RECT, brush: win.HBRUSH) callconv(.winapi) c_int;
extern "user32" fn DrawTextW(hdc: win.HDC, text: win.LPCWSTR, len: c_int, rect: *win.RECT, format: u32) callconv(.winapi) c_int;
extern "user32" fn LoadImageW(inst: ?win.HINSTANCE, name: *const anyopaque, kind: u32, cx: c_int, cy: c_int, flags: u32) callconv(.winapi) ?*anyopaque;
extern "user32" fn LoadCursorW(inst: ?win.HINSTANCE, name: *const anyopaque) callconv(.winapi) ?win.HCURSOR;
extern "user32" fn LoadIconW(inst: ?win.HINSTANCE, name: *const anyopaque) callconv(.winapi) ?win.HICON;
extern "user32" fn DrawIconEx(hdc: win.HDC, x: c_int, y: c_int, icon: win.HICON, w: c_int, h: c_int, step: u32, brush: ?win.HBRUSH, flags: u32) callconv(.winapi) win.BOOL;
extern "user32" fn GetClientRect(hwnd: win.HWND, rect: *win.RECT) callconv(.winapi) win.BOOL;
extern "user32" fn MoveWindow(hwnd: win.HWND, x: c_int, y: c_int, w: c_int, h: c_int, repaint: win.BOOL) callconv(.winapi) win.BOOL;
extern "user32" fn SendMessageW(hwnd: win.HWND, msg: u32, wparam: usize, lparam: isize) callconv(.winapi) isize;
extern "user32" fn GetDC(hwnd: ?win.HWND) callconv(.winapi) ?win.HDC;
extern "user32" fn ReleaseDC(hwnd: ?win.HWND, hdc: win.HDC) callconv(.winapi) c_int;
extern "user32" fn SetProcessDPIAware() callconv(.winapi) win.BOOL;
extern "user32" fn MessageBoxW(hwnd: ?win.HWND, text: win.LPCWSTR, caption: win.LPCWSTR, kind: u32) callconv(.winapi) c_int;
extern "user32" fn DestroyWindow(hwnd: win.HWND) callconv(.winapi) win.BOOL;
extern "gdi32" fn GetDeviceCaps(hdc: win.HDC, index: c_int) callconv(.winapi) c_int;
extern "gdi32" fn CreateSolidBrush(color: u32) callconv(.winapi) ?win.HBRUSH;
extern "gdi32" fn CreateFontW(
    height: c_int,
    width: c_int,
    escapement: c_int,
    orientation: c_int,
    weight: c_int,
    italic: win.DWORD,
    underline: win.DWORD,
    strike: win.DWORD,
    charset: win.DWORD,
    out_precision: win.DWORD,
    clip_precision: win.DWORD,
    quality: win.DWORD,
    pitch: win.DWORD,
    face: win.LPCWSTR,
) callconv(.winapi) ?*anyopaque;
extern "gdi32" fn SelectObject(hdc: win.HDC, obj: ?*anyopaque) callconv(.winapi) ?*anyopaque;
extern "gdi32" fn SetBkMode(hdc: win.HDC, mode: c_int) callconv(.winapi) c_int;
extern "gdi32" fn SetTextColor(hdc: win.HDC, color: u32) callconv(.winapi) u32;
extern "gdi32" fn GetStockObject(obj: c_int) callconv(.winapi) ?*anyopaque;
extern "gdi32" fn RoundRect(hdc: win.HDC, left: c_int, top: c_int, right: c_int, bottom: c_int, width: c_int, height: c_int) callconv(.winapi) win.BOOL;
extern "gdi32" fn Polygon(hdc: win.HDC, points: [*]const win.POINT, count: c_int) callconv(.winapi) win.BOOL;
extern "shell32" fn ShellExecuteW(
    hwnd: ?win.HWND,
    operation: win.LPCWSTR,
    file: win.LPCWSTR,
    params: ?win.LPCWSTR,
    dir: ?win.LPCWSTR,
    show: c_int,
) callconv(.winapi) isize;

var app_instance: win.HINSTANCE = undefined;
var main_window: ?win.HWND = null;
var open_button: ?win.HWND = null;
var logo_icon: ?win.HICON = null;
var title_font: ?*anyopaque = null;
var body_font: ?*anyopaque = null;
var dpi: u32 = 96;
var bg_brush: ?win.HBRUSH = null;
var navy_brush: ?win.HBRUSH = null;
var teal_brush: ?win.HBRUSH = null;
var sea_brush: ?win.HBRUSH = null;
var foam_brush: ?win.HBRUSH = null;

fn rgb(r: u32, g: u32, b: u32) u32 {
    return r | (g << 8) | (b << 16);
}

fn intResource(comptime id: comptime_int) *const anyopaque {
    return @ptrFromInt(id);
}

fn px(value: i32) i32 {
    return @divTrunc(value * @as(i32, @intCast(dpi)), 96);
}

fn wide(comptime text: []const u8) win.LPCWSTR {
    @setEvalBranchQuota(4000);
    return std.unicode.utf8ToUtf16LeStringLiteral(text);
}

const class_name = wide("KhromiumWindow");
const title_w = wide(copy.title);
const body_w = wide(copy.body);
const hint_w = wide(copy.hint);
const button_w = wide(copy.button_label);
const site_w = wide(copy.site_url);
const open_verb = wide("open");
const failed_w = wide(copy.open_failed);
const face_w = wide("Segoe UI");

fn screenDpi() u32 {
    const hdc = GetDC(null) orelse return 96;
    const value = GetDeviceCaps(hdc, LOGPIXELSX);
    _ = ReleaseDC(null, hdc);
    if (value < 96) return 96;
    return @intCast(value);
}

fn makeFont(height: i32, weight: c_int) ?*anyopaque {
    return CreateFontW(-height, 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 5, 0, face_w);
}

fn loadAppIcon(side: c_int) ?win.HICON {
    const raw = LoadImageW(app_instance, intResource(1), IMAGE_ICON, side, side, 0) orelse return null;
    return @ptrCast(raw);
}

fn openSite() void {
    // No other address is passed to the shell. site_url is a fixed local page.
    if (!copy.isSiteUrl(copy.site_url)) return;
    const result = ShellExecuteW(main_window, open_verb, site_w, null, null, SW_SHOWNORMAL);
    if (result <= 32) {
        _ = MessageBoxW(main_window, failed_w, title_w, 0x40);
    }
}

fn layout(hwnd: win.HWND) void {
    const button = open_button orelse return;
    var client: win.RECT = std.mem.zeroes(win.RECT);
    if (GetClientRect(hwnd, &client) == 0) return;
    const bw = px(260);
    const bh = px(40);
    const x = px(268);
    const y = client.bottom - px(32) - bh;
    _ = MoveWindow(button, x, y, bw, bh, 1);
}

fn createControls(hwnd: win.HWND) void {
    title_font = makeFont(px(30), FW_BOLD);
    body_font = makeFont(px(16), FW_NORMAL);
    const menu: ?win.HMENU = @ptrFromInt(button_id);
    open_button = CreateWindowExW(
        0,
        wide("BUTTON"),
        button_w,
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
        px(268),
        px(360),
        px(260),
        px(40),
        hwnd,
        menu,
        app_instance,
        null,
    );
    if (open_button) |button| {
        if (body_font) |font| {
            _ = SendMessageW(button, 0x0030, @intFromPtr(font), 1);
        }
    }
    layout(hwnd);
}

fn paintText(hdc: win.HDC, font: ?*anyopaque, color: u32, text: win.LPCWSTR, rect: *win.RECT) void {
    _ = SetBkMode(hdc, TRANSPARENT);
    _ = SetTextColor(hdc, color);
    if (font) |chosen| {
        _ = SelectObject(hdc, chosen);
    }
    _ = DrawTextW(hdc, text, -1, rect, DT_WORDBREAK | DT_NOPREFIX);
}

fn mapLogo(origin_x: i32, origin_y: i32, side: i32, x: i32, y: i32) win.POINT {
    return .{
        .x = origin_x + @divTrunc(x * side, 256),
        .y = origin_y + @divTrunc(y * side, 256),
    };
}

fn paintPolygon(hdc: win.HDC, brush: ?win.HBRUSH, origin_x: i32, origin_y: i32, side: i32, coords: []const [2]i32) void {
    const chosen = brush orelse return;
    var points: [8]win.POINT = undefined;
    if (coords.len > points.len) return;
    for (coords, 0..) |pair, index| {
        points[index] = mapLogo(origin_x, origin_y, side, pair[0], pair[1]);
    }
    _ = SelectObject(hdc, @ptrCast(chosen));
    _ = Polygon(hdc, &points, @intCast(coords.len));
}

fn paintGeometricLogo(hdc: win.HDC, origin_x: i32, origin_y: i32, side: i32) void {
    const pen = GetStockObject(NULL_PEN);
    _ = SelectObject(hdc, pen);
    if (navy_brush) |brush| {
        _ = SelectObject(hdc, @ptrCast(brush));
        const radius = @divTrunc(side * 58, 128);
        _ = RoundRect(hdc, origin_x, origin_y, origin_x + side, origin_y + side, radius, radius);
    }
    // Same 256-space polygons as assets/logo.svg.
    const upper = [_][2]i32{ .{ 93, 155 }, .{ 201, 75 }, .{ 171, 33 }, .{ 63, 113 } };
    const lower = [_][2]i32{ .{ 63, 143 }, .{ 171, 223 }, .{ 201, 181 }, .{ 93, 101 } };
    const stem = [_][2]i32{ .{ 50, 40 }, .{ 114, 40 }, .{ 114, 216 }, .{ 50, 216 } };
    paintPolygon(hdc, teal_brush, origin_x, origin_y, side, &upper);
    paintPolygon(hdc, sea_brush, origin_x, origin_y, side, &lower);
    paintPolygon(hdc, foam_brush, origin_x, origin_y, side, &stem);
}

fn paintLogo(hdc: win.HDC, origin_x: i32, origin_y: i32, side: i32) void {
    if (logo_icon) |icon| {
        if (DrawIconEx(hdc, origin_x, origin_y, icon, side, side, 0, null, DI_NORMAL) != 0) return;
    }
    paintGeometricLogo(hdc, origin_x, origin_y, side);
}

fn paint(hwnd: win.HWND) void {
    var ps: PAINTSTRUCT = undefined;
    const hdc = BeginPaint(hwnd, &ps) orelse return;
    defer _ = EndPaint(hwnd, &ps);

    var client: win.RECT = std.mem.zeroes(win.RECT);
    _ = GetClientRect(hwnd, &client);
    if (bg_brush) |brush| {
        _ = FillRect(hdc, &client, brush);
    }

    const side = px(200);
    paintLogo(hdc, px(36), px(40), side);

    const ink = rgb(8, 36, 63);
    const muted = rgb(26, 78, 104);
    var title_rect = win.RECT{
        .left = px(268),
        .top = px(44),
        .right = client.right - px(32),
        .bottom = px(96),
    };
    var body_rect = win.RECT{
        .left = px(268),
        .top = px(108),
        .right = client.right - px(32),
        .bottom = px(280),
    };
    var hint_rect = win.RECT{
        .left = px(268),
        .top = client.bottom - px(108),
        .right = client.right - px(32),
        .bottom = client.bottom - px(80),
    };
    paintText(hdc, title_font, ink, title_w, &title_rect);
    paintText(hdc, body_font, ink, body_w, &body_rect);
    paintText(hdc, body_font, muted, hint_w, &hint_rect);
}

fn wndProc(hwnd: win.HWND, message: win.UINT, wparam: win.WPARAM, lparam: win.LPARAM) callconv(.winapi) win.LRESULT {
    switch (message) {
        WM_CREATE => {
            main_window = hwnd;
            createControls(hwnd);
            return 0;
        },
        WM_SIZE => {
            layout(hwnd);
            return 0;
        },
        WM_COMMAND => {
            const id: u16 = @truncate(wparam);
            if (id == button_id) openSite();
            return 0;
        },
        WM_KEYDOWN => {
            if (wparam == VK_RETURN) openSite();
            return 0;
        },
        WM_PAINT => {
            paint(hwnd);
            return 0;
        },
        WM_CLOSE => {
            _ = DestroyWindow(hwnd);
            return 0;
        },
        WM_DESTROY => {
            PostQuitMessage(0);
            return 0;
        },
        else => return DefWindowProcW(hwnd, message, wparam, lparam),
    }
}

pub fn run() u8 {
    _ = SetProcessDPIAware();
    dpi = screenDpi();

    const module = GetModuleHandleW(null) orelse return 1;
    app_instance = @ptrCast(module);
    logo_icon = loadAppIcon(256);
    const class_icon = loadAppIcon(32) orelse LoadIconW(null, intResource(32512));
    const small_icon = loadAppIcon(16) orelse class_icon;

    bg_brush = CreateSolidBrush(rgb(244, 248, 251));
    navy_brush = CreateSolidBrush(rgb(8, 36, 63));
    teal_brush = CreateSolidBrush(rgb(30, 212, 198));
    sea_brush = CreateSolidBrush(rgb(58, 160, 255));
    foam_brush = CreateSolidBrush(rgb(245, 251, 255));

    const wc = WNDCLASSEXW{
        .cbSize = @sizeOf(WNDCLASSEXW),
        .style = CS_HREDRAW | CS_VREDRAW,
        .lpfnWndProc = &wndProc,
        .cbClsExtra = 0,
        .cbWndExtra = 0,
        .hInstance = app_instance,
        .hIcon = class_icon,
        .hCursor = LoadCursorW(null, intResource(32512)),
        .hbrBackground = bg_brush,
        .lpszMenuName = null,
        .lpszClassName = class_name,
        .hIconSm = small_icon,
    };
    if (RegisterClassExW(&wc) == 0) return 1;

    const style = WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_CLIPCHILDREN;
    const hwnd = CreateWindowExW(
        0,
        class_name,
        title_w,
        style,
        @bitCast(@as(u32, 0x80000000)),
        @bitCast(@as(u32, 0x80000000)),
        px(780),
        px(480),
        null,
        null,
        app_instance,
        null,
    ) orelse return 1;
    main_window = hwnd;

    _ = ShowWindow(hwnd, SW_SHOW);
    _ = UpdateWindow(hwnd);

    var message: MSG = undefined;
    while (true) {
        const status = GetMessageW(&message, null, 0, 0);
        if (status == 0) break;
        if (status < 0) return 1;
        if (message.message == WM_KEYDOWN and message.wParam == VK_RETURN) {
            openSite();
            continue;
        }
        _ = TranslateMessage(&message);
        _ = DispatchMessageW(&message);
    }
    return 0;
}
