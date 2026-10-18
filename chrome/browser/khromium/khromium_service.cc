// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/khromium/khromium_service.h"

#include <algorithm>
#include <optional>
#include <utility>

#include "base/files/file_util.h"
#include "base/functional/bind.h"
#include "base/task/thread_pool.h"
#include "base/time/time.h"
#include "chrome/browser/khromium/ai_client.h"
#include "chrome/browser/khromium/khromium_service_factory.h"
#include "chrome/browser/profiles/profile.h"
#include "components/khromium/features.h"
#include "components/prefs/pref_registry_simple.h"
#include "components/prefs/pref_service.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/storage_partition.h"
#include "net/base/registry_controlled_domains/registry_controlled_domain.h"
#include "services/network/public/cpp/shared_url_loader_factory.h"

namespace khromium {
namespace {

constexpr size_t kMaxSnippetBytes = 12 * 1024;
constexpr size_t kMaxQueuedAnalyzes = 8;
constexpr size_t kMaxNotedScripts = 8;

}  // namespace

// static
void KhromiumService::RegisterProfilePrefs(PrefRegistrySimple* registry) {
  registry->RegisterBooleanPref(prefs::kAiShieldEnabled, true);
  registry->RegisterStringPref(prefs::kProvider, "openai");
  registry->RegisterIntegerPref(prefs::kCacheTtlHours, 24 * 7);
}

// static
void KhromiumService::BindFrameAgent(
    content::RenderFrameHost* host,
    mojo::PendingReceiver<mojom::KhromiumAgent> receiver) {
  if (!host) {
    return;
  }
  KhromiumService* service =
      KhromiumServiceFactory::GetForBrowserContext(host->GetBrowserContext());
  if (!service) {
    return;
  }
  service->receivers_.Add(service, std::move(receiver), host);
}

// static
KhromiumService::DiskState KhromiumService::ReadDisk(
    base::FilePath dir,
    std::string provider_pref) {
  DiskState state;
  // `dir` is <profile>/khromium, which lives inside the user data directory.
  // Also accept <user data dir>/Khromium/config.json so one key file can cover
  // every profile. Environment variables win inside LoadAiConfig.
  base::CreateDirectory(dir);
  base::ReadFileToStringWithMaxSize(dir.AppendASCII("analysis_cache.json"),
                                    &state.cache_json, 1024 * 1024);
  const base::FilePath profile_config = dir.AppendASCII("ai_config.json");
  const base::FilePath user_data_config =
      dir.DirName().AppendASCII("Khromium").AppendASCII("config.json");
  const base::FilePath config_path = base::PathExists(profile_config)
                                         ? profile_config
                                         : user_data_config;
  state.config = LoadAiConfig(config_path, provider_pref);
  return state;
}

KhromiumService::KhromiumService(content::BrowserContext* context)
    : context_(context),
      prefs_(Profile::FromBrowserContext(context)->GetPrefs()),
      dir_(context->GetPath().AppendASCII("khromium")) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  auto factory = context_->GetDefaultStoragePartition()
                     ->GetURLLoaderFactoryForBrowserProcess();
  client_ = std::make_unique<AiClient>(std::move(factory));
  StartDiskLoad();
}

KhromiumService::~KhromiumService() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
}

void KhromiumService::Shutdown() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  receivers_.Clear();
  client_.reset();
  weak_factory_.InvalidateWeakPtrs();
}

bool KhromiumService::IsEntitled() const {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  return ready_ && ShieldEnabled();
}

base::WeakPtr<KhromiumService> KhromiumService::GetWeakPtr() {
  return weak_factory_.GetWeakPtr();
}

bool KhromiumService::ShieldEnabled() const {
  return base::FeatureList::IsEnabled(kKhromiumAiAdShield) &&
         prefs_->GetBoolean(prefs::kAiShieldEnabled);
}

base::TimeDelta KhromiumService::CacheTtl() const {
  int hours = prefs_->GetInteger(prefs::kCacheTtlHours);
  if (hours < 1) {
    hours = 1;
  }
  if (hours > 24 * 30) {
    hours = 24 * 30;
  }
  return base::Hours(hours);
}

std::string KhromiumService::RegistrableDomain(const GURL& url) const {
  std::string domain = net::registry_controlled_domains::GetDomainAndRegistry(
      url, net::registry_controlled_domains::INCLUDE_PRIVATE_REGISTRIES);
  if (domain.empty()) {
    domain = url.GetHost();
  }
  return domain;
}

void KhromiumService::NoteSuspiciousScript(const GURL& page,
                                           const GURL& script) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (!page.SchemeIsHTTPOrHTTPS() || !script.is_valid()) {
    return;
  }
  const std::string domain = RegistrableDomain(page);
  if (domain.empty()) {
    return;
  }
  std::vector<std::string>& noted = noted_scripts_[domain];
  if (noted.size() >= kMaxNotedScripts) {
    return;
  }
  std::string spec = script.spec();
  if (spec.size() > 300) {
    spec.resize(300);
  }
  if (std::find(noted.begin(), noted.end(), spec) == noted.end()) {
    noted.push_back(std::move(spec));
  }
}

void KhromiumService::StartDiskLoad() {
  const std::string provider = prefs_->GetString(prefs::kProvider);
  base::ThreadPool::PostTaskAndReplyWithResult(
      FROM_HERE, {base::MayBlock(), base::TaskPriority::USER_VISIBLE},
      base::BindOnce(&KhromiumService::ReadDisk, dir_, provider),
      base::BindOnce(&KhromiumService::OnDisk, weak_factory_.GetWeakPtr()));
}

void KhromiumService::OnDisk(DiskState state) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  cache_.LoadFromJson(state.cache_json, base::Time::Now(), CacheTtl());
  if (client_) {
    client_->set_config(std::move(state.config));
  }
  // The feature flag and profile pref are the switch. There is no license.
  entitled_ = true;
  FinishStartup();
}

void KhromiumService::FinishStartup() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  ready_ = true;
  FlushQueued();
}

void KhromiumService::FlushQueued() {
  std::vector<IsEntitledCallback> waiters;
  waiters.swap(entitled_waiters_);
  for (auto& waiter : waiters) {
    std::move(waiter).Run(ShieldEnabled());
  }
  std::vector<QueuedAnalyze> queued;
  queued.swap(queued_);
  for (auto& item : queued) {
    Dispatch(std::move(item.page), std::move(item.snippet),
             std::move(item.callback));
  }
}

mojom::AnalysisDecisionPtr KhromiumService::MakeDecision(
    bool block,
    std::vector<std::string> selectors,
    bool restore_scroll,
    const std::string& reason,
    bool from_cache) const {
  auto decision = mojom::AnalysisDecision::New();
  decision->block = block;
  decision->selectors = std::move(selectors);
  decision->restore_scroll = restore_scroll;
  decision->reason = reason;
  decision->from_cache = from_cache;
  return decision;
}

KhromiumService::PageCapture KhromiumService::CapturePage() const {
  PageCapture page;
  content::RenderFrameHost* host = receivers_.current_context();
  if (!host) {
    return page;
  }
  page.url = host->GetLastCommittedURL();
  page.domain = RegistrableDomain(page.url);
  return page;
}

void KhromiumService::IsEntitled(IsEntitledCallback callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (!ShieldEnabled()) {
    std::move(callback).Run(false);
    return;
  }
  if (!ready_) {
    entitled_waiters_.push_back(std::move(callback));
    return;
  }
  std::move(callback).Run(true);
}

void KhromiumService::Analyze(const std::string& trimmed_snippet,
                              AnalyzeCallback callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  PageCapture page = CapturePage();
  std::string snippet = trimmed_snippet.substr(0, kMaxSnippetBytes);
  if (!ShieldEnabled()) {
    std::move(callback).Run(
        MakeDecision(false, {}, false, "Khromium is turned off", false));
    return;
  }
  if (!ready_) {
    if (queued_.size() >= kMaxQueuedAnalyzes) {
      std::move(callback).Run(MakeDecision(
          false, {}, false, "Khromium is still loading its config", false));
      return;
    }
    queued_.push_back(QueuedAnalyze{std::move(page), std::move(snippet),
                                    std::move(callback)});
    return;
  }
  Dispatch(std::move(page), std::move(snippet), std::move(callback));
}

void KhromiumService::Dispatch(PageCapture page,
                               std::string snippet,
                               AnalyzeCallback callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (!page.url.SchemeIsHTTPOrHTTPS() || page.domain.empty()) {
    std::move(callback).Run(
        MakeDecision(false, {}, false, "Unsupported page", false));
    return;
  }
  if (snippet.empty()) {
    std::move(callback).Run(
        MakeDecision(false, {}, false, "No suspicious snippet", false));
    return;
  }

  const auto noted = noted_scripts_.find(page.domain);
  if (noted != noted_scripts_.end()) {
    for (const std::string& script : noted->second) {
      if (snippet.find(script) != std::string::npos) {
        continue;
      }
      const std::string line = "\nscript: " + script;
      if (snippet.size() + line.size() > kMaxSnippetBytes) {
        break;
      }
      snippet.append(line);
    }
  }

  const base::Time now = base::Time::Now();
  if (std::optional<AnalysisDecision> cached =
          cache_.Lookup(page.domain, now, CacheTtl())) {
    std::move(callback).Run(MakeDecision(cached->block, cached->selectors,
                                         cached->restore_scroll, cached->reason,
                                         true));
    return;
  }

  auto inflight = inflight_.find(page.domain);
  if (inflight != inflight_.end()) {
    inflight->second.push_back(std::move(callback));
    return;
  }
  inflight_[page.domain].push_back(std::move(callback));
  if (!client_ || !client_->config().has_key()) {
    // Do not cache a missing key: the user may add one without deleting the
    // domain cache. Also never log the key or the config path contents.
    OnClassified(page.domain, /*cache_negative_on_failure=*/false,
                 std::nullopt);
    return;
  }
  const std::string domain = page.domain;
  client_->Classify(
      std::move(snippet),
      base::BindOnce(&KhromiumService::OnClassified, weak_factory_.GetWeakPtr(),
                     domain, /*cache_negative_on_failure=*/true));
}

void KhromiumService::OnClassified(
    std::string domain,
    bool cache_negative_on_failure,
    std::optional<AnalysisDecision> decision) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  mojom::AnalysisDecisionPtr mojo_decision;
  if (!decision) {
    if (cache_negative_on_failure) {
      // One attempt per domain, including a transport failure, so a dead
      // endpoint cannot add a request to every navigation.
      AnalysisDecision negative;
      negative.block = false;
      negative.restore_scroll = false;
      negative.reason = "model request failed";
      cache_.Store(domain, negative, base::Time::Now());
      PersistCache();
    }
    mojo_decision =
        MakeDecision(false, {}, false, "Model request failed", false);
  } else {
    cache_.Store(domain, *decision, base::Time::Now());
    PersistCache();
    mojo_decision =
        MakeDecision(decision->block, decision->selectors,
                     decision->restore_scroll, decision->reason, false);
  }
  Reply(std::move(domain), std::move(mojo_decision));
}

void KhromiumService::Reply(std::string domain,
                            mojom::AnalysisDecisionPtr decision) {
  std::vector<AnalyzeCallback> waiters;
  auto it = inflight_.find(domain);
  if (it != inflight_.end()) {
    waiters.swap(it->second);
    inflight_.erase(it);
  }
  for (size_t i = 0; i < waiters.size(); ++i) {
    if (i + 1 == waiters.size()) {
      std::move(waiters[i]).Run(std::move(decision));
    } else {
      std::move(waiters[i]).Run(decision.Clone());
    }
  }
}

void KhromiumService::PersistCache() {
  const std::string json = cache_.ToJson();
  const base::FilePath path = dir_.AppendASCII("analysis_cache.json");
  base::ThreadPool::PostTask(
      FROM_HERE, {base::MayBlock(), base::TaskPriority::BEST_EFFORT},
      base::BindOnce(
          [](base::FilePath path, std::string json) {
            base::CreateDirectory(path.DirName());
            base::WriteFile(path, json);
          },
          path, json));
}

}  // namespace khromium
