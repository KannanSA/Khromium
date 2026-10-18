// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_KHROMIUM_AI_CLIENT_H_
#define CHROME_BROWSER_KHROMIUM_AI_CLIENT_H_

#include <deque>
#include <memory>
#include <string>

#include "base/functional/callback.h"
#include "base/memory/weak_ptr.h"
#include "chrome/browser/khromium/ai_config.h"
#include "components/khromium/decision.h"
#include "services/network/public/cpp/shared_url_loader_factory.h"

namespace network {
class SimpleURLLoader;
}

namespace khromium {

// Asynchronous chat-completions client. Create and use it on the UI thread.
// Download callbacks are posted by SimpleURLLoader; this class never blocks.
class AiClient {
 public:
  using Callback = base::OnceCallback<void(std::optional<AnalysisDecision>)>;

  explicit AiClient(scoped_refptr<network::SharedURLLoaderFactory> factory);
  ~AiClient();

  AiClient(const AiClient&) = delete;
  AiClient& operator=(const AiClient&) = delete;

  void set_config(AiConfig config) { config_ = std::move(config); }
  const AiConfig& config() const { return config_; }

  // `snippet` is the trimmed DOM context. The API key is attached as a
  // request header and is not written to logs.
  void Classify(std::string snippet, Callback callback);

 private:
  struct Job {
    std::string snippet;
    Callback callback;
  };

  void StartNext();
  void OnComplete(std::optional<std::string> body);

  scoped_refptr<network::SharedURLLoaderFactory> factory_;
  AiConfig config_;
  std::deque<Job> queue_;
  std::unique_ptr<network::SimpleURLLoader> loader_;
  Callback active_callback_;
  base::WeakPtrFactory<AiClient> weak_factory_{this};
};

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_AI_CLIENT_H_
