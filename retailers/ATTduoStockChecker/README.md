# ATTduoStockChecker — investigation only

Not a working stock checker. No verified store-level inventory adapter or scheduled workflow has been implemented.

Target: iPhone Duo, Star White, 256GB, NY/NJ AT&T stores.
Verified product listing: https://www.att.com/buy/phones/apple-iphone-duo-256gb-star-white.html

Next requirement: inspect the public pickup selection flow, identify the exact product identifier and store-inventory response, validate a request for a known store, and establish whether corporate and authorized retailer locations are covered. An accessible product page or store directory does not establish inventory availability. Never infer sold out from a blocked request, missing store or missing data. Do not reuse Apple's part number as an AT&T identifier without validation.

No credentials are required or stored in this project. No endpoint has been invented. No all-store coverage is claimed.
