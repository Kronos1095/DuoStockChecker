# AT&T Duo pickup checker

Implemented in DuoStockChecker. Targets iPhone Duo, Star White, 256GB: AT&T SKU sku57765v2, bill code 6050G, extracted from the exact product page on November 2, 2026.

Uses the same public POST request as AT&T's product pickup modal:
`/msapi/sales/uis/v1/inventory/storeavailability?zipCode=10001`
Body: `{"itemDetails":[{"category":"phone","billCode":"6050G"}]}`.

Live local validation: 10001 and 07001 returned UIS-INV-00003 (Items out of stock). This is a ZIP-search negative, not proof each store is sold out. The successful nonempty response parser follows the site's JavaScript content.storeList, availableQuantity, inv_id and region fields; an in-stock live response has not yet been observed. Cloud-runner access remains to be validated.

Runs 24 ZIP searches across NY/NJ. Missing/error responses are unknown. Does not claim exhaustive store coverage or independently operated retailer coverage. Excludes returned stores outside NY/NJ. No alert sending yet. No API key or account required for the tested public endpoint.

Output: docs/att-status.json. Workflow: Check AT&T NY NJ (manual and hourly). Run locally: python retailers/ATTduoStockChecker/monitor.py. Tests: python -m unittest discover -s retailers/ATTduoStockChecker -v.

Sources: https://www.att.com/buy/phones/apple-iphone-duo-256gb-star-white.html and its public JavaScript chunk 6780.10ddbfa647391ca2.js under /buy/pdpnxetc/_next/static/chunks/.
