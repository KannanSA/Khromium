// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_KHROMIUM_KHROMIUM_SERVICE_H_
#define CHROME_BROWSER_KHROMIUM_KHROMIUM_SERVICE_H_

#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "base/files/file_path.h"
#include "base/memory/raw_ptr.h"
#include "base/memory/weak_ptr.h"
#include "base/sequence_checker.h"
#include "chrome/browser/khromium/ai_config.h"
#include "chrome/browser/khromium/analysis_cache.h"
#include "components/keyed_service/core/keyed_service.h"
#include "components/khromium/mojom/khromium.mojom.h"
#include "mojo/public/cpp/bindings/pending_receiver.h"
#include "mojo/public/cpp/bindings/receiver_set.h"
#include "url/gurl.h"

class PrefRegistrySimple;
class PrefService;

namespace content {
class BrowserContext;
class RenderFrameHost;
}

namespace khromium {

class AiClient;

// Browser-process owner of the per-domain cache and the async model client.
// Bound to renderers through KhromiumAgent. All methods run on the UI thread.
// Disk IO and HTTP are posted off the UI thread and never block it. The model
// API key stays in this process.
class KhromiumService : public KeyedService, public mojom::KhromiumAgent {
 public:
  explicit KhromiumService(content::BrowserContext* context);
  ~KhromiumService() override;

  KhromiumService(const KhromiumService&) = delete;
  KhromiumService& operator=(const KhromiumService&) = delete;

  static void RegisterProfilePrefs(PrefRegistrySimple* registry);

  static void BindFrameAgent(
      content::RenderFrameHost* host,
      mojo::PendingReceiver<mojom::KhromiumAgent> receiver);

  // Records a script URL the URLLoaderThrottle saw. The next Analyze for that
  // registrable domain includes it. Does not cancel the load.
  void NoteSuspiciousScript(const GURL& page, const GURL& script);

  // True after startup once the feature flag and profile pref are both on.
  bool IsEntitled() const;

  base::WeakPtr<KhromiumService> GetWeakPtr();

  // KeyedService:
  void Shutdown() override;

  // mojom::KhromiumAgent:
  void IsEntitled(IsEntitledCallback callback) override;
  void Analyze(const std::string& trimmed_snippet,
               AnalyzeCallback callback) override;

 private:
  struct PageCapture {
    GURL url;
    std::string domain;
  };

  struct DiskState {
    std::string license_key;
    std::string license_server;
    std::string cache_json;
    AiConfig config;
  };

  struct QueuedAnalyze {
    PageCapture page;
    std::string snippet;
    AnalyzeCallback callback;
  };

  static DiskState ReadDisk(base::FilePath dir, std::string provider_pref);

  bool ShieldEnabled() const;
  base::TimeDelta CacheTtl() const;
  PageCapture CapturePage() const;
  std::string RegistrableDomain(const GURL& url) const;
  mojom::AnalysisDecisionPtr MakeDecision(bool block,
                                          std::vector<std::string> selectors,
                                          bool restore_scroll,
                                          const std::string& reason,
                                          bool from_cache) const;
  void StartDiskLoad();
  void OnDisk(DiskState state);
  void FinishStartup();
  void FlushQueued();
  void Dispatch(PageCapture page,
                std::string snippet,
                AnalyzeCallback callback);
  void OnClassified(std::string domain,
                    bool cache_negative_on_failure,
                    std::optional<AnalysisDecision> decision);
  void PersistCache();
  void Reply(std::string domain, mojom::AnalysisDecisionPtr decision);

  raw_ptr<content::BrowserContext> context_;
  raw_ptr<PrefService> prefs_;
  base::FilePath dir_;
  AnalysisCache cache_;
  std::unique_ptr<AiClient> client_;

  bool ready_ = false;
  bool entitled_ = false;
  std::vector<IsEntitledCallback> entitled_waiters_;
  std::vector<QueuedAnalyze> queued_;
  std::map<std::string, std::vector<AnalyzeCallback>> inflight_;
  std::map<std::string, std::vector<std::string>> noted_scripts_;

  mojo::ReceiverSet<mojom::KhromiumAgent, content::RenderFrameHost*> receivers_;

  SEQUENCE_CHECKER(sequence_checker_);
  base::WeakPtrFactory<KhromiumService> weak_factory_{this};
};

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_KHROMIUM_SERVICE_H_
