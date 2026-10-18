// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef CHROME_RENDERER_KHROMIUM_KHROMIUM_DETECTOR_H_
#define CHROME_RENDERER_KHROMIUM_KHROMIUM_DETECTOR_H_

#include <stdint.h>

#include "base/memory/weak_ptr.h"
#include "components/khromium/mojom/khromium.mojom.h"
#include "content/public/renderer/render_frame_observer.h"
#include "mojo/public/cpp/bindings/remote.h"

namespace khromium {

// Renderer hook. Asks the browser whether AI protection is active before
// reading the DOM. An ended trial stops the scan. The provider API key
// never enters this process.
class KhromiumDetector : public content::RenderFrameObserver {
 public:
  explicit KhromiumDetector(content::RenderFrame* render_frame);
  ~KhromiumDetector() override;

  KhromiumDetector(const KhromiumDetector&) = delete;
  KhromiumDetector& operator=(const KhromiumDetector&) = delete;

  // content::RenderFrameObserver:
  void DidFinishLoad() override;
  void OnDestruct() override;

 private:
  void OnEntitled(uint64_t generation, bool entitled);
  void Scan(uint64_t generation);
  void OnScanResult(uint64_t generation,
                    std::optional<base::Value> results,
                    base::TimeTicks start_time);
  void OnDecision(uint64_t generation, mojom::AnalysisDecisionPtr decision);

  mojo::Remote<mojom::KhromiumAgent> agent_;
  uint64_t generation_ = 0;
  base::WeakPtrFactory<KhromiumDetector> weak_factory_{this};
};

}  // namespace khromium

#endif  // CHROME_RENDERER_KHROMIUM_KHROMIUM_DETECTOR_H_
