// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef COMPONENTS_KHROMIUM_LICENSE_TOKEN_H_
#define COMPONENTS_KHROMIUM_LICENSE_TOKEN_H_

#include <cstdint>
#include <string>
#include <string_view>

namespace khromium {

struct LicenseStatus {
  // Lasting browser purchase. True for plan "browser" while `exp` is in the
  // future. A monthly AI plan does not set this.
  bool entitled_browser = false;
  // AI trial or monthly AI plan. True only while `ai_until` is in the future.
  // An ended trial leaves entitled_browser alone.
  bool entitled_ai = false;
  std::string plan;
  int64_t expires_unix = 0;
  int64_t ai_until_unix = 0;
  // Safe to log. Never contains the key or the HMAC secret.
  std::string detail;
};

// Local HMAC check used when KHROMIUM_LICENSE_SERVER is unset.
// Token form: KHRO1.<base64url payload json>.<base64url hmac-sha256>
// Payload keys: plan (browser|ai_monthly), sub, exp, ai_until, v (1).
// The HMAC covers the payload segment exactly, using
// KHROMIUM_LICENSE_HMAC_SECRET or the development secret.
// `exp` is the browser entitlement. For a browser purchase it is far in the
// future. For ai_monthly it is the end of the paid month, and that plan does
// not grant entitled_browser.
LicenseStatus VerifyLicenseToken(std::string_view token, int64_t now_unix);

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_LICENSE_TOKEN_H_
