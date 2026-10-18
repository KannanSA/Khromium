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
  return plan == "browser" || plan == "ai_monthly";
}

std::optional<int64_t> FindUnix(const base::DictValue& dict,
                                std::string_view key) {
  // FindDouble accepts both JSON ints and doubles.
  const std::optional<double> value = dict.FindDouble(key);
  if (!value) {
    return std::nullopt;
  }
  return static_cast<int64_t>(*value);
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
  const std::optional<int64_t> exp = FindUnix(*dict, "exp");
  const std::optional<int64_t> ai_until = FindUnix(*dict, "ai_until");
  const std::optional<double> version = dict->FindDouble("v");
  if (!plan || !KnownPlan(*plan) || !exp || *exp <= 0 || !version ||
      static_cast<int64_t>(*version) != 1) {
    status.detail = "license payload is invalid";
    return status;
  }
  status.plan = *plan;
  status.expires_unix = *exp;
  status.ai_until_unix = ai_until.value_or(0);
  const bool browser_plan = *plan == "browser";
  const bool ai_plan = *plan == "ai_monthly";
  // Monthly AI does not keep browser rights after the month, and does not
  // grant them during the month either. The browser purchase is the plan
  // that keeps entitled_browser after the AI trial ends.
  status.entitled_browser = browser_plan && status.expires_unix > now_unix;
  status.entitled_ai =
      (browser_plan || ai_plan) && status.ai_until_unix > now_unix;
  if (status.entitled_browser && status.entitled_ai) {
    status.detail = "browser license active; AI trial active";
  } else if (status.entitled_browser) {
    status.detail = "browser license active; AI protection has ended";
  } else if (status.entitled_ai) {
    status.detail = "monthly AI plan active";
  } else if (ai_plan) {
    status.detail = "monthly AI plan has expired";
  } else {
    status.detail = "browser license has expired";
  }
  return status;
}

}  // namespace khromium
