// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/khromium/ai_client.h"

#include "base/json/json_writer.h"
#include "base/time/time.h"
#include "base/values.h"
#include "components/khromium/system_prompt.h"
#include "net/traffic_annotation/network_traffic_annotation.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/cpp/simple_url_loader.h"
#include "services/network/public/mojom/url_response_head.mojom.h"
#include "url/gurl.h"

namespace khromium {
namespace {

constexpr size_t kMaxResponseBytes = 64 * 1024;

net::NetworkTrafficAnnotationTag KhromiumTrafficAnnotation() {
  return net::DefineNetworkTrafficAnnotation("khromium_shield_chat", R"(
    semantics {
      sender: "Khromium Shield"
      description:
        "Sends a trimmed snippet of a page that looks like an anti-adblock "
        "wall or an obfuscated ad container to the configured chat "
        "completions API (OpenAI or xAI Grok) so the browser can decide "
        "whether to hide that overlay."
      trigger:
        "KhromiumAiAdShield is enabled, the profile pref is on, and the "
        "renderer found a suspicious overlay on a site that is not already "
        "in the per-domain cache."
      data:
        "Registrable-domain context is implied by the snippet. The snippet "
        "may contain visible text and selectors from the page. The API key "
        "is sent as an Authorization header. Cookies are not sent."
      destination: WEBSITE
      internal {
        contacts {
          email: "khromium-shield@localhost"
        }
      }
      user_data {
        type: SENSITIVE_URL
        type: WEB_CONTENT
      }
      last_reviewed: "2026-10-18"
    }
    policy {
      cookies_allowed: NO
      setting:
        "Disabled unless KhromiumAiAdShield is enabled and the profile pref "
        "khromium.ai_shield_enabled is true. Both default to off for the "
        "feature flag and on for the pref, so the flag is the opt-in."
      policy_exception_justification:
        "Khromium is a fork preference, not an upstream enterprise policy."
    })");
}

std::string BuildRequestBody(const AiConfig& config, const std::string& snippet) {
  base::DictValue body;
  body.Set("model", config.model);
  body.Set("temperature", 0.0);
  base::DictValue response_format;
  response_format.Set("type", "json_object");
  body.Set("response_format", std::move(response_format));

  base::ListValue messages;
  base::DictValue system;
  system.Set("role", "system");
  system.Set("content", std::string(GetSystemPrompt()));
  messages.Append(std::move(system));
  base::DictValue user;
  user.Set("role", "user");
  user.Set("content", snippet);
  messages.Append(std::move(user));
  body.Set("messages", std::move(messages));

  std::optional<std::string> json = base::WriteJson(body);
  return json.value_or(std::string());
}

}  // namespace

AiClient::AiClient(scoped_refptr<network::SharedURLLoaderFactory> factory)
    : factory_(std::move(factory)) {}

AiClient::~AiClient() = default;

void AiClient::Classify(std::string snippet, Callback callback) {
  queue_.push_back(Job{std::move(snippet), std::move(callback)});
  if (!loader_) {
    StartNext();
  }
}

void AiClient::StartNext() {
  if (queue_.empty() || !factory_) {
    return;
  }
  if (!config_.has_key() || config_.endpoint.empty()) {
    Job job = std::move(queue_.front());
    queue_.pop_front();
    std::move(job.callback).Run(std::nullopt);
    StartNext();
    return;
  }

  Job job = std::move(queue_.front());
  queue_.pop_front();
  active_callback_ = std::move(job.callback);

  const std::string body = BuildRequestBody(config_, job.snippet);
  if (body.empty()) {
    std::move(active_callback_).Run(std::nullopt);
    StartNext();
    return;
  }

  auto request = std::make_unique<network::ResourceRequest>();
  request->url = GURL(config_.endpoint);
  request->method = "POST";
  request->credentials_mode = network::mojom::CredentialsMode::kOmit;
  // The key stays in the header. Do not log `request->headers`.
  request->headers.SetHeader("Authorization", "Bearer " + config_.api_key);
  request->headers.SetHeader("Content-Type", "application/json");

  loader_ = network::SimpleURLLoader::Create(std::move(request),
                                             KhromiumTrafficAnnotation());
  loader_->AttachStringForUpload(body, "application/json");
  loader_->SetAllowHttpErrorResults(true);
  loader_->SetTimeoutDuration(base::Seconds(20));
  loader_->DownloadToString(
      factory_.get(),
      base::BindOnce(&AiClient::OnComplete, weak_factory_.GetWeakPtr()),
      kMaxResponseBytes);
}

void AiClient::OnComplete(std::optional<std::string> body) {
  int response_code = 0;
  if (loader_ && loader_->ResponseInfo() && loader_->ResponseInfo()->headers) {
    response_code = loader_->ResponseInfo()->headers->response_code();
  }
  const int net_error = loader_ ? loader_->NetError() : -1;
  loader_.reset();

  std::optional<AnalysisDecision> decision;
  if (net_error == 0 && response_code >= 200 && response_code < 300 && body) {
    decision = ParseChatCompletionBody(*body);
  }
  // Intentionally not logging `body`: it can echo page content.
  if (active_callback_) {
    std::move(active_callback_).Run(std::move(decision));
  }
  StartNext();
}

}  // namespace khromium
