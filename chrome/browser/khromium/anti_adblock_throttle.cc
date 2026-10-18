// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#include "chrome/browser/khromium/anti_adblock_throttle.h"

#include "base/feature_list.h"
#include "base/functional/bind.h"
#include "base/strings/string_util.h"
#include "base/task/single_thread_task_runner.h"
#include "chrome/browser/khromium/khromium_service.h"
#include "chrome/browser/khromium/khromium_service_factory.h"
#include "chrome/browser/profiles/profile.h"
#include "components/khromium/features.h"
#include "components/khromium/script_patterns.h"
#include "components/prefs/pref_service.h"
#include "content/public/browser/browser_thread.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/mojom/fetch_api.mojom.h"

namespace khromium {

// static
std::unique_ptr<AntiAdblockThrottle> AntiAdblockThrottle::MaybeCreate(
    Profile* profile,
    const GURL& page_url) {
  if (!profile || !base::FeatureList::IsEnabled(kKhromiumAiAdShield) ||
      !profile->GetPrefs()->GetBoolean(prefs::kAiShieldEnabled)) {
    return nullptr;
  }
  KhromiumService* service =
      KhromiumServiceFactory::GetForBrowserContext(profile);
  // Paid gate. The throttle is created per request, so this becomes true
  // after the license file has been checked.
  if (!service || !service->IsEntitled()) {
    return nullptr;
  }
  return std::make_unique<AntiAdblockThrottle>(
      base::BindRepeating(&KhromiumService::NoteSuspiciousScript,
                          service->GetWeakPtr()),
      page_url);
}

AntiAdblockThrottle::AntiAdblockThrottle(NoteCallback note, GURL page_url)
    : note_(std::move(note)), page_url_(std::move(page_url)) {}

AntiAdblockThrottle::~AntiAdblockThrottle() = default;

void AntiAdblockThrottle::WillStartRequest(network::ResourceRequest* request,
                                           bool* defer) {
  if (defer) {
    *defer = false;
  }
  if (!request ||
      request->destination != network::mojom::RequestDestination::kScript) {
    return;
  }
  const std::string url = base::ToLowerASCII(request->url.spec());
  bool matched = false;
  for (std::string_view marker : kAntiAdblockScriptMarkers) {
    if (url.find(marker) != std::string::npos) {
      matched = true;
      break;
    }
  }
  if (!matched || !note_) {
    return;
  }
  GURL page = page_url_;
  if (!page.SchemeIsHTTPOrHTTPS() && request->referrer.is_valid()) {
    page = request->referrer;
  }
  const GURL script = request->url;
  // WillStartRequest may run off the UI thread. The callback is a WeakPtr
  // bound on the UI thread, so it is only invoked there.
  content::GetUIThreadTaskRunner({})->PostTask(
      FROM_HERE, base::BindOnce(note_, page, script));
}

}  // namespace khromium
