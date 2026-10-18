// Copyright 2026 The Khromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/renderer/khromium/khromium_detector.h"

#include "base/containers/span.h"
#include "base/feature_list.h"
#include "base/functional/bind.h"
#include "base/task/single_thread_task_runner.h"
#include "base/time/time.h"
#include "base/values.h"
#include "chrome/common/chrome_isolated_world_ids.h"
#include "chrome/renderer/khromium/page_script.h"
#include "components/khromium/features.h"
#include "content/public/renderer/render_frame.h"
#include "third_party/blink/public/platform/scheduler/web_agent_group_scheduler.h"
#include "third_party/blink/public/platform/web_string.h"
#include "third_party/blink/public/web/web_document.h"
#include "third_party/blink/public/web/web_local_frame.h"
#include "third_party/blink/public/web/web_script_source.h"
#include "url/gurl.h"
#include "v8/include/v8-isolate.h"

namespace khromium {

KhromiumDetector::KhromiumDetector(content::RenderFrame* render_frame)
    : content::RenderFrameObserver(render_frame) {}

KhromiumDetector::~KhromiumDetector() = default;

void KhromiumDetector::OnDestruct() {
  delete this;
}

void KhromiumDetector::DidFinishLoad() {
  if (!render_frame() || !render_frame()->IsMainFrame()) {
    return;
  }
  if (!base::FeatureList::IsEnabled(kKhromiumAiAdShield)) {
    return;
  }
  blink::WebLocalFrame* frame = render_frame()->GetWebFrame();
  if (!frame) {
    return;
  }
  const GURL url(frame->GetDocument().Url());
  if (!url.SchemeIsHTTPOrHTTPS()) {
    return;
  }
  const uint64_t generation = ++generation_;
  if (!agent_) {
    render_frame()->GetBrowserInterfaceBroker().GetInterface(
        agent_.BindNewPipeAndPassReceiver());
  }
  agent_->IsEntitled(base::BindOnce(&KhromiumDetector::OnEntitled,
                                    weak_factory_.GetWeakPtr(), generation));
}

void KhromiumDetector::OnEntitled(uint64_t generation, bool entitled) {
  if (generation != generation_ || !entitled || !render_frame()) {
    return;
  }
  Scan(generation);
  base::SingleThreadTaskRunner::GetCurrentDefault()->PostDelayedTask(
      FROM_HERE,
      base::BindOnce(&KhromiumDetector::Scan, weak_factory_.GetWeakPtr(),
                     generation),
      base::Seconds(2));
}

void KhromiumDetector::Scan(uint64_t generation) {
  if (generation != generation_ || !render_frame()) {
    return;
  }
  blink::WebLocalFrame* frame = render_frame()->GetWebFrame();
  if (!frame) {
    return;
  }
  v8::HandleScope handle_scope(frame->GetAgentGroupScheduler()->Isolate());
  blink::WebScriptSource source(blink::WebString::FromUtf8(HeuristicScanScript()));
  frame->RequestExecuteScript(
      ISOLATED_WORLD_ID_CHROME_INTERNAL, base::span_from_ref(source),
      blink::mojom::UserActivationOption::kDoNotActivate,
      blink::mojom::EvaluationTiming::kAsynchronous,
      blink::mojom::LoadEventBlockingOption::kDoNotBlock,
      base::BindOnce(&KhromiumDetector::OnScanResult, weak_factory_.GetWeakPtr(),
                     generation),
      blink::BackForwardCacheAware::kAllow,
      blink::mojom::WantResultOption::kWantResult,
      blink::mojom::PromiseResultOption::kDoNotWait,
      blink::WebString());
}

void KhromiumDetector::OnScanResult(uint64_t generation,
                                   std::optional<base::Value> results,
                                   base::TimeTicks start_time) {
  if (generation != generation_ || !results || !results->is_string() ||
      !agent_) {
    return;
  }
  const std::string& snippet = results->GetString();
  if (snippet.empty()) {
    return;
  }
  agent_->Analyze(snippet, base::BindOnce(&KhromiumDetector::OnDecision,
                                          weak_factory_.GetWeakPtr(),
                                          generation));
}

void KhromiumDetector::OnDecision(uint64_t generation,
                                 mojom::AnalysisDecisionPtr decision) {
  if (generation != generation_ || !decision || !render_frame()) {
    return;
  }
  if (!decision->block && !decision->restore_scroll) {
    return;
  }
  blink::WebLocalFrame* frame = render_frame()->GetWebFrame();
  if (!frame) {
    return;
  }
  v8::HandleScope handle_scope(frame->GetAgentGroupScheduler()->Isolate());
  const std::string source_text =
      CleanupScript(decision->selectors, decision->restore_scroll);
  blink::WebScriptSource source(blink::WebString::FromUtf8(source_text));
  frame->RequestExecuteScript(
      ISOLATED_WORLD_ID_CHROME_INTERNAL, base::span_from_ref(source),
      blink::mojom::UserActivationOption::kDoNotActivate,
      blink::mojom::EvaluationTiming::kAsynchronous,
      blink::mojom::LoadEventBlockingOption::kDoNotBlock,
      base::BindOnce([](std::optional<base::Value>, base::TimeTicks) {}),
      blink::BackForwardCacheAware::kAllow,
      blink::mojom::WantResultOption::kNoResult,
      blink::mojom::PromiseResultOption::kDoNotWait,
      blink::WebString());
}

}  // namespace khromium
