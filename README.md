# Duo Stock Watch — NY/NJ

Personal tracker for iPhone Duo Star White 256GB. Apple configuration MK1E4LL/A; AT&T SKU sku57765v2 / bill code 6050G; Best Buy AT&T SKU 6525566.

## Current behavior

One workflow checks retailers concurrently and publishes all status files with serialized, non-overlapping runs. GitHub's shortest supported cron interval is five minutes; the schedule is offset from the top of the hour to reduce contention. Schedules can be delayed and are not real-time guarantees. No always-on server or paid runner is required.

Apple: 16 regional ZIP searches with three concurrent workers. AT&T: 24 ZIP searches with three workers. Regional results do not prove every NY/NJ store was checked. AT&T explicit UIS-INV-00003 is a ZIP-level out-of-stock response, not a per-store result. Both public endpoints are undocumented and can change or block cloud requests.

Best Buy: the public GraphQL product query was accessible, but fulfillment returned code 401, including the exact query observed in the retailer page. No keyless store checker is claimed. The official API adapter requires BESTBUY_API_KEY. That adapter is not live-validated with a real key. It enumerates NY/NJ stores with pagination and checks each store ID sequentially at no more than four calls/sec.

## Dashboard and alerts

Enable Pages from main /docs. The dashboard displays all three retailers, coverage, unknown/setup states, last success, notification configuration and stale data after 15 minutes. Refreshing the dashboard does not request new inventory. Availability is not a reservation; confirm pickup dates before checkout.

Optional Actions secret NTFY_TOPIC enables alerts only for a known unavailable-to-available store transition with the same product identifier. First scans and unknown-to-available observations do not alert. ntfy topic names are private configuration, but public ntfy topics are not access-controlled. Notification errors do not invalidate stock results. Delivery is not exactly-once and failed sends are not automatically retried.

## Reliability

Two bounded attempts for network errors, HTTP 429 and selected 5xx; Retry-After honored up to 15 seconds, longer throttling left to next run. Authentication failures are not retried. Each adapter has a 180-second overall execution budget; failed results clear current stores and retain old data only as lastKnownStores history. Atomic writes prevent half-written JSON. All scheduled publishing uses a single concurrency group and a bounded rebase/push retry. Never print secret-bearing request URLs.

Run `python -m unittest discover -s tests -v`, then `python run_all.py`. Python 3.12+, standard library only. Missing Best Buy credentials are explicitly setup_required. Set APPLE_PART_NUMBER as a repository variable only to override the default. No secrets belong in repository files or docs.

Sources: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule ; https://bestbuyapis.github.io/api-documentation/ ; https://www.att.com/buy/phones/apple-iphone-duo-256gb-star-white.html
