# NYC Stock Watch — iPad / GitHub Pages edition

Tracks Apple pickup inventory for **iPhone Duo, Star White, 256GB** at NYC-area Apple Stores using two ZIP lookups (10001 and 10314). Includes an iPad-friendly dashboard and ntfy alerts.

## Setup from iPad Safari

1. Create a **private or public GitHub repository** and upload these files, preserving `.github/workflows/check.yml` and `docs/`. The Pages site is public if enabled; don't put secrets in `docs/`.
2. In repository **Settings → Secrets and variables → Actions → Variables**, add `APPLE_PART_NUMBER` with the **verified US Apple part number** for the Star White 256GB Duo. Find it by selecting that configuration on Apple's website and inspecting the `parts.0` field of its `pickup-message` network request on a desktop browser. **No part number has been verified for this model yet. Do not substitute a retailer SKU or guess.**
3. Install the **ntfy** iPad app and subscribe to a long random topic, e.g. `nyc-duo-` followed by 25+ random characters. In GitHub Actions **Secrets**, add `NTFY_TOPIC` containing that exact topic. ntfy public topics are not access-controlled; anyone who learns the topic can subscribe.
4. Open **Actions → Check Apple pickup → Run workflow**. Examine its logs. An HTTP 541, 403, or malformed response is a **failed check**, not sold out. Cloud-hosted GitHub IP addresses may be blocked by Apple.
5. In **Settings → Pages**, choose **Deploy from a branch**, branch `main`, folder `/docs`. Open the Pages URL from Safari and use **Share → Add to Home Screen**.
6. GitHub Actions is scheduled every **5 minutes**, but execution may be delayed or disabled for inactive repositories. Free-tier quotas and GitHub policies apply. Alerts fire only when a store transitions from a previously successfully observed unavailable state to available.

## Limitations

- **Not deployed**: you must create the repository and set variables/secrets in your own GitHub account.
- **Apple API not live-validated** in this environment. The undocumented `/shop/retail/pickup-message` endpoint has been reported working from residential IPs but sometimes blocked on cloud IPs. If blocked, the dashboard reports an error; a different authorized source or hosting arrangement will be needed.
- Part number is **not yet verified**. Monitor deliberately refuses to claim availability until configured.
- GitHub Actions schedule is not guaranteed real-time. Fast-selling inventory may be missed.
- The dashboard is publicly visible when hosted on GitHub Pages. It contains store statuses only, no notification secret.
- No purchase automation. No subscription required, subject to third-party free-tier limits.

## Local validation

Run `python -m unittest discover -s tests -v` and `python monitor.py` (without a SKU it writes `setup_required`).
