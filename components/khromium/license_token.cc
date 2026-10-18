// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#include "components/khromium/license_token.h"

#include <algorithm>
#include <array>
#include <vector>

#include "base/base64.h"
#include "base/containers/span.h"
#include "base/environment.h"
#include "base/json/json_reader.h"
#include "base/strings/string_split.h"
#include "base/strings/string_util.h"
#include "crypto/hash.h"
#include "crypto/hmac.h"

namespace khromium {
namespace {

constexpr std::string_view kDevSecret = "khromium-dev-license-hmac-v1";

std::string HmacSecret() {
  std::unique_ptr<base::Environment> env = base::Environment::Create();
  std::optional<std::string> override =
      env->GetVar("KHROMIUM_LICENSE_HMAC_SECRET");
  if (override && !override->empty()) {
    return *override;
  }
  return std::string(kDevSecret);
}

std::string Base64UrlToStandard(std::string_view in) {
  std::string out;
  out.reserve(in.size() + 3);
  for (char c : in) {
    if (c == '-') {
      out.push_back('+');
    } else if (c == '_') {
      out.push_back('/');
    } else {
      out.push_back(c);
    }
  }
  while (out.size() % 4) {
    out.push_back('=');
  }
  return out;
}

std::optional<std::vector<uint8_t>> DecodeUrl(std::string_view in) {
  if (in.empty()) {
    return std::nullopt;
  }
  return base::Base64Decode(Base64UrlToStandard(in));
}

bool KnownPlan(std::string_view plan) {
  return plan == "monthly" || plan == "yearly" || plan == "lifetime";
}

}  // namespace

LicenseStatus VerifyLicenseToken(std::string_view token, int64_t now_unix) {
  LicenseStatus status;
  const std::string trimmed(
      base::TrimWhitespaceASCII(token, base::TRIM_ALL));
  const std::vector<std::string> parts = base::SplitString(
      trimmed, ".", base::KEEP_WHITESPACE, base::SPLIT_WANT_ALL);
  if (parts.size() != 3 || parts[0] != "KHRO1") {
    status.detail = "license key format is invalid";
    return status;
  }

  std::optional<std::vector<uint8_t>> payload = DecodeUrl(parts[1]);
  std::optional<std::vector<uint8_t>> mac = DecodeUrl(parts[2]);
  if (!payload || !mac || mac->size() != crypto::hash::kSha256Size) {
    status.detail = "license key signature is invalid";
    return status;
  }

  std::array<uint8_t, crypto::hash::kSha256Size> mac_bytes{};
  std::copy(mac->begin(), mac->end(), mac_bytes.begin());
  const std::string secret = HmacSecret();
  if (!crypto::hmac::VerifySha256(base::as_byte_span(secret),
                                  base::as_byte_span(parts[1]), mac_bytes)) {
    status.detail = "license key signature is invalid";
    return status;
  }

  const std::string json(payload->begin(), payload->end());
  std::optional<base::DictValue> dict =
      base::JSONReader::ReadDict(json, base::JSON_PARSE_RFC);
  if (!dict) {
    status.detail = "license payload is invalid";
    return status;
  }
  const std::string* plan = dict->FindString("plan");
  const std::optional<double> exp = dict->FindDouble("exp");
  if (!plan || !KnownPlan(*plan) || !exp) {
    status.detail = "license payload is invalid";
    return status;
  }
  status.plan = *plan;
  status.expires_unix = static_cast<int64_t>(*exp);
  if (status.expires_unix <= now_unix) {
    status.detail = "license has expired";
    return status;
  }
  status.entitled = true;
  status.detail = "paid subscription active";
  return status;
}

}  // namespace khromium
