// Copyright 2026 Khromium. All rights reserved.
// Proprietary commercial software. See //LICENSE.khromium.

#ifndef CHROME_BROWSER_KHROMIUM_KHROMIUM_SERVICE_FACTORY_H_
#define CHROME_BROWSER_KHROMIUM_KHROMIUM_SERVICE_FACTORY_H_

#include "components/keyed_service/content/browser_context_keyed_service_factory.h"

namespace content {
class BrowserContext;
}

namespace khromium {

class KhromiumService;

class KhromiumServiceFactory : public BrowserContextKeyedServiceFactory {
 public:
  static KhromiumService* GetForBrowserContext(content::BrowserContext* context);
  static KhromiumServiceFactory* GetInstance();

  KhromiumServiceFactory(const KhromiumServiceFactory&) = delete;
  KhromiumServiceFactory& operator=(const KhromiumServiceFactory&) = delete;

 private:
  friend class base::NoDestructor<KhromiumServiceFactory>;

  KhromiumServiceFactory();
  ~KhromiumServiceFactory() override;

  std::unique_ptr<KeyedService> BuildServiceInstanceForBrowserContext(
      content::BrowserContext* context) const override;
  content::BrowserContext* GetBrowserContextToUse(
      content::BrowserContext* context) const override;
};

}  // namespace khromium

#endif  // CHROME_BROWSER_KHROMIUM_KHROMIUM_SERVICE_FACTORY_H_
