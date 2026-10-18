// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

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

namespace network {
class SimpleURLLoader;
}

namespace khromium {

class AiClient;

// Browser-process owner of the paid license, the per-domain cache, and the
// async model client. Bound to renderers through KhromiumAgent. All methods
// run on the UI thread. Disk IO and HTTP are posted off the UI thread and
// never block it. The license key stays in this process. The provider API
// key stays on the Khromium proxy unless KHROMIUM_ALLOW_BYO_KEY=1.
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

  // True only when startup has finished, the feature is on, and AI
  // protection is still inside `ai_until` (trial or monthly plan). False
  // while the check is in flight, and false after the trial ends even if
  // the browser purchase is still valid. The renderer uses this to decide
  // whether it may copy DOM.
  bool IsEntitled() const;

  // True when a browser purchase is still inside `exp`. This stays true
  // after the included AI trial ends. A monthly AI plan does not set it.
  bool IsBrowserLicensed() const;

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
  void StartOnlineLicenseCheck(const std::string& server, const std::string& key);
  void OnLicenseResponse(std::optional<std::string> body);
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
  std::unique_ptr<network::SimpleURLLoader> license_loader_;

  bool ready_ = false;
  bool entitled_browser_ = false;
  bool entitled_ai_ = false;
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
