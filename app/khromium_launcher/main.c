/* Copyright 2026 Khromium. All rights reserved.
 * Proprietary commercial software. See LICENSE.khromium at the repo root.
 *
 * Khromium launcher. This is the paid companion, not the full browser.
 * It does not collect card numbers and it does not embed Stripe keys.
 */

#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#else
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;
#endif

static const char kInfo[] =
    "Khromium\n"
    "========\n"
    "Khromium launcher. This program opens the local download site.\n"
    "It is not the full Khromium browser, and it is not Google Chrome.\n"
    "\n"
    "Khromium is an independent project and is not affiliated with Google.\n"
    "\n"
    "Offers (published defaults)\n"
    "  Browser, once     $49.00\n"
    "                    One-time purchase. Includes 30 days of AI ad-block.\n"
    "                    After 30 days the browser license remains and AI stops.\n"
    "  Monthly AI        $10.00 per month\n"
    "                    Twice the API cost (default API cost $5.00).\n"
    "                    AI only. Khromium holds the model key.\n"
    "\n"
    "This program does not collect card numbers and does not contain\n"
    "Stripe secret keys. The download site sends buyers to Stripe-hosted\n"
    "Checkout. Card numbers stay on Stripe.\n"
    "\n"
    "Start the local download site from a Khromium checkout:\n"
    "  cd app/khromium_site\n"
    "  python3 -m khromium_site --port 8787\n"
    "Then open http://127.0.0.1:8787\n"
    "\n"
    "Usage\n"
    "  khromium                 Show this page\n"
    "  khromium --open          Open http://127.0.0.1:8787\n"
    "  khromium --open URL      Open http://127.0.0.1 or http://localhost\n"
    "                           (optional port and path)\n";

static void print_info(void) {
    fputs(kInfo, stdout);
    fflush(stdout);
}

#ifdef _WIN32
static const char kDialog[] =
    "Khromium\n"
    "\n"
    "Browser, once: $49.00\n"
    "Includes 30 days of AI ad-block.\n"
    "\n"
    "Monthly AI: $10.00 per month\n"
    "Twice the API cost.\n"
    "\n"
    "This is the Khromium launcher, not the full browser.\n"
    "Khromium is not Google Chrome.\n"
    "\n"
    "It does not collect card numbers.\n"
    "\n"
    "Start the download site:\n"
    "  cd app/khromium_site\n"
    "  python3 -m khromium_site --port 8787\n"
    "\n"
    "Or run this program with --open";

static void show_dialog(void) {
    MessageBoxA(NULL, kDialog, "Khromium", MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
}
#endif

/* http://127.0.0.1[:port][/path] or http://localhost[:port][/path]. */
static int local_site_url(const char *url) {
    const char *rest;
    const char *scan;
    size_t length;
    char port_text[8];
    size_t port_len;
    unsigned port;
    size_t i;

    if (!url) {
        return 0;
    }
    length = strlen(url);
    if (length == 0 || length > 200) {
        return 0;
    }
    /* Dot-dot would leave the site root after the browser resolves it. */
    if (strstr(url, "..") != NULL || strchr(url, '\\') != NULL) {
        return 0;
    }
    if (strncmp(url, "http://127.0.0.1", 16) == 0) {
        rest = url + 16;
    } else if (strncmp(url, "http://localhost", 16) == 0) {
        rest = url + 16;
    } else {
        return 0;
    }
    if (*rest == '\0') {
        return 1;
    }
    if (*rest == '/') {
        scan = rest;
    } else if (*rest == ':') {
        rest++;
        port_len = 0;
        while (rest[port_len] && rest[port_len] != '/') {
            if (port_len + 1 >= sizeof(port_text)) {
                return 0;
            }
            if (rest[port_len] < '0' || rest[port_len] > '9') {
                return 0;
            }
            port_text[port_len] = rest[port_len];
            port_len++;
        }
        if (port_len == 0) {
            return 0;
        }
        port_text[port_len] = '\0';
        port = 0;
        for (i = 0; i < port_len; i++) {
            port = port * 10u + (unsigned)(port_text[i] - '0');
            if (port > 65535u) {
                return 0;
            }
        }
        if (port < 1u) {
            return 0;
        }
        scan = rest + port_len;
        if (*scan == '\0') {
            return 1;
        }
        if (*scan != '/') {
            return 0;
        }
    } else {
        return 0;
    }
    for (; *scan; scan++) {
        char c = *scan;
        int ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                 (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '~' ||
                 c == '/' || c == '-';
        if (!ok) {
            return 0;
        }
    }
    return 1;
}

static int open_url(const char *url) {
#ifdef _WIN32
    wchar_t wide[256];
    int converted;
    HINSTANCE result;

    converted = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, url, -1, wide, 256);
    if (converted <= 0) {
        return 1;
    }
    result = ShellExecuteW(NULL, L"open", wide, NULL, NULL, SW_SHOWNORMAL);
    return ((INT_PTR)result > 32) ? 0 : 1;
#else
    pid_t pid;
    int err;
    int status = 0;
#ifdef __APPLE__
    char *argv[] = {"/usr/bin/open", (char *)url, NULL};
    const char *program = "/usr/bin/open";
#else
    char *argv[] = {"xdg-open", (char *)url, NULL};
    const char *program = "/usr/bin/xdg-open";
#endif
    if (access(program, X_OK) != 0) {
        return 1;
    }
    err = posix_spawn(&pid, program, NULL, NULL, argv, environ);
    if (err != 0) {
        return 1;
    }
    if (waitpid(pid, &status, 0) < 0) {
        return 1;
    }
    return status == 0 ? 0 : 1;
#endif
}

static void open_failed(const char *url) {
    fprintf(stderr, "Khromium: could not open a browser for %s\n", url);
    fputs("Start the download site, then visit that address:\n", stderr);
    fputs("  cd app/khromium_site\n", stderr);
    fputs("  python3 -m khromium_site --port 8787\n", stderr);
}

int main(int argc, char **argv) {
    const char *url = "http://127.0.0.1:8787";
    int opening = 0;

    if (argc == 1) {
        print_info();
#ifdef _WIN32
        show_dialog();
#endif
        return 0;
    }
    if (argc == 2 && (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0)) {
        print_info();
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "--open") == 0) {
        opening = 1;
    } else if (argc == 3 && strcmp(argv[1], "--open") == 0) {
        opening = 1;
        url = argv[2];
    } else {
        fputs("Khromium: unknown arguments. Try --help.\n", stderr);
        return 2;
    }
    print_info();
    if (!opening) {
        return 0;
    }
    if (!local_site_url(url)) {
        fprintf(stderr,
                "Khromium: refusing to open '%s'.\n"
                "Only http://127.0.0.1 and http://localhost are allowed.\n",
                url);
        return 1;
    }
    printf("Opening %s\n", url);
    fflush(stdout);
    if (open_url(url) != 0) {
        open_failed(url);
        return 1;
    }
    return 0;
}
