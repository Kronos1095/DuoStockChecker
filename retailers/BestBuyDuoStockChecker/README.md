# BestBuyDuoStockChecker

Included in DuoStockChecker; not live-validated.
Tracks SKU 6525566: iPhone Duo Star White 256GB (AT&T).
Enumerates NY and NJ stores with the official Stores API, then checks each store ID through the documented SKU availability endpoint. Unknown checks remain unknown; coverage totals are explicit.

Obtain an API key at https://developer.bestbuy.com/ and add BESTBUY_API_KEY as a repository Actions secret. Never commit the key. Run python retailers/BestBuyDuoStockChecker/monitor.py with Python 3.12+. The bundled workflow runs manually and hourly from .github/workflows/bestbuy.yml. Output: retailers/BestBuyDuoStockChecker/status.json. No push alerts yet. Per-store queries may hit API limits; failures are reported as unknown. API access and mobile SKU support must be tested with a real key before relying on results.

Sources:
- https://bestbuyapis.github.io/api-documentation/#in-store-availability
- https://www.bestbuy.com/product/apple-iphone-duo-256gb-star-white-at-t/6525566
