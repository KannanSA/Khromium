// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef CHROME_BROWSER_KHROMIUM_ANTI_ADBLOCK_THROTTLE_H_
#define CHROME_BROWSER_KHROMIUM_ANTI_ADBLOCK_THROTTLE_H_

#include <memory>

#include "base/functional/callback.h"
#include "third_party/blink/public/common/loader/url_loader_throttle.h"
#include "url/gurl.h"

class Profile;

namespace khromium {

class KhromiumService;

// Browser-side URLLoaderThrottle. Watches script URLs for a short list of
// known anti-adblock libraries and records a hit on KhromiumService.
//
// The load is not cancelled or deferred. Blocking the script is itself a
// signal many anti-adblock kits look for, and the decision to hide a wall
// belongs to the DOM scan plus the model, not to a URL denylist.
class AntiAdblockThrottle : public blink::URLLoaderThrottle {
 public:
  static std::unique_ptr<AntiAdblockThrottle> MaybeCreate(Profile* profile,
                                                          const GURL& page_url);

  using NoteCallback = base::RepeatingCallback<void(const GURL& page, const GURL& script)>;

  AntiAdblockThrottle(NoteCallback note, GURL page_url);
  ~AntiAdblockThrottle() override;

  void WillStartRequest(network::ResourceRequest* request,
                        bool* defer) override;

 private:
  AntiAdblockThrottle(const AntiAdblockThrottle&) = delete;
  AntiAdblockThrottle& operator=(const AntiAdblockThrottle&) = delete;

  // Bound on the UI thread to a WeakPtr. WillStartRequest only posts it.
  NoteCallback note_;
  GURL page_url_;
};

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_ANTI_ADBLOCK_THROTTLE_H_
