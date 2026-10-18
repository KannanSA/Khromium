// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#include "chrome/browser/khromium/khromium_service_factory.h"

#include "base/no_destructor.h"
#include "chrome/browser/khromium/khromium_service.h"
#include "components/keyed_service/content/browser_context_dependency_manager.h"
#include "components/keyed_service/core/keyed_service.h"

namespace khromium {

// static
KhromiumService* KhromiumServiceFactory::GetForBrowserContext(
    content::BrowserContext* context) {
  return static_cast<KhromiumService*>(
      GetInstance()->GetServiceForBrowserContext(context, /*create=*/true));
}

// static
KhromiumServiceFactory* KhromiumServiceFactory::GetInstance() {
  static base::NoDestructor<KhromiumServiceFactory> factory;
  return factory.get();
}

KhromiumServiceFactory::KhromiumServiceFactory()
    : BrowserContextKeyedServiceFactory(
          "KhromiumService",
          BrowserContextDependencyManager::GetInstance()) {}

KhromiumServiceFactory::~KhromiumServiceFactory() = default;

std::unique_ptr<KeyedService>
KhromiumServiceFactory::BuildServiceInstanceForBrowserContext(
    content::BrowserContext* context) const {
  return std::make_unique<KhromiumService>(context);
}

content::BrowserContext* KhromiumServiceFactory::GetBrowserContextToUse(
    content::BrowserContext* context) const {
  return context;
}

}  // namespace khromium
