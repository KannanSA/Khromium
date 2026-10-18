// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef COMPONENTS_KHROMIUM_LICENSE_TOKEN_H_
#define COMPONENTS_KHROMIUM_LICENSE_TOKEN_H_

#include <cstdint>
#include <string>
#include <string_view>

namespace khromium {

struct LicenseStatus {
  bool entitled = false;
  std::string plan;
  int64_t expires_unix = 0;
  // Safe to log. Never contains the key or the HMAC secret.
  std::string detail;
};

// Local HMAC check used when KHROMIUM_LICENSE_SERVER is unset.
// Token form: KHRO1.<base64url payload json>.<base64url hmac-sha256>
// Payload keys: plan (monthly|yearly|lifetime), sub, exp (unix seconds).
// The HMAC covers the payload segment exactly, using
// KHROMIUM_LICENSE_HMAC_SECRET or the development secret.
LicenseStatus VerifyLicenseToken(std::string_view token, int64_t now_unix);

}  // namespace khromium

#endif  // COMPONENTS_KHROMIUM_LICENSE_TOKEN_H_
