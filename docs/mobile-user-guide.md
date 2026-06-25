# Mobile User Guide — Sentinel on Your Phone

> For iOS and Android users: visit, sign up, and get stock alerts on your device.

---

## Quick Start (3 minutes)

**1. Open the site**

Go to [**https://web-weld-six-79.vercel.app**](https://web-weld-six-79.vercel.app) in Safari (iOS) or Chrome (Android). You'll see the Sentinel landing page with a ticker search box.

**2. Create an account**

Tap **Sign In** (top-right), then tap **Create an account** at the bottom of the sign-in card. Fill in:
- **Username** — your login name
- **Display name** (optional) — how your name appears in the app
- **Password** — at least 4 characters

Tap **Create Account**. You'll be logged in automatically and taken to your watchlist.

**3. Add stocks to watch**

On the watchlist page, tap the search bar at the top, type a ticker (e.g. `AAPL`, `TSLA`, `MSFT`), and tap **Track** on the result. Your watchlist populates with health scores, price data, and risk flags for each stock.

**4. Choose how to get alerts**

Sentinel delivers alerts in two ways. Set up one or both in **Settings** (click your username in the sidebar):

| Channel | How it works | iOS | Android |
|---|---|---|---|
| **Web Push** | Browser notification, like a text from an app | Requires adding to Home Screen first (see below) | Works directly in Chrome |
| **Telegram** | You connect a Telegram bot; alerts arrive as Telegram messages | Works with any Telegram client | Works with any Telegram client |

**For Web Push (recommended for most users):**
- **Android** — Tap **Enable Web Push** in Settings. Chrome asks for notification permission — tap **Allow**. Done.
- **iOS** — Web push requires an extra step (see next section).

**For Telegram:**
1. Open Telegram and search for [@BotFather](https://t.me/botfather).
2. Send `/newbot`, pick a name, and copy the bot token it gives you (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`).
3. In Sentinel Settings, paste the token into the **Bot Token** field and tap **Connect**.
4. Send `/start` to your bot in Telegram to link your account.

**5. Configure what triggers alerts**

In **Settings**, scroll to **Notification Preferences**. Check the boxes for events you care about:
- Health score changes
- Verdict changes (e.g. "Strong Buy" → "Moderate")
- New risk flags
- Z-Score zone changes
- F-Score changes

Adjust the **Check Interval** (how often the system re-evaluates your stocks, 1–24 hours) and the **Health Score Change Threshold** (how many points a score must shift before it fires an alert). Tap **Save Preferences**.

You can also add custom alert rules on the **Alerts** page — things like "alert me when AAPL drops below $170" or "when P/E ratio exceeds 30."

**6. You're set**

Alerts now run 24/7 on Sentinel's server. When a condition triggers, you'll get a push notification or Telegram message — even if you close the browser tab.

---

## iOS: Getting Web Push to Work

iOS Safari blocks web push notifications unless you install the site as a **Progressive Web App** (PWA). Here's how:

1. Open the site in Safari.
2. Tap the **Share** button (square with arrow at the bottom of the screen).
3. Scroll down and tap **Add to Home Screen**.
4. Tap **Add** (top-right). Sentinel now appears as an app icon on your home screen.
5. Open Sentinel from the **Home Screen icon** (not Safari).
6. Go to **Settings** and tap **Enable Web Push** — it will work now.

After this, push notifications behave like any other iOS app notification. You can manage them in **Settings → Notifications** on your iPhone.

> If you skip the Home Screen step, the Enable Web Push button will show a message explaining this requirement.

---

## Managing Notifications

**View past alerts:** Open the **Notifications** page from the sidebar. Filter by severity (Info / Warning / Critical), ticker, or type (News / Alerts / Health). Tap the checkmark icon to mark a notification as read, or **Mark All Read** to clear them.

**Disable notifications anytime:** Go to **Settings** and tap **Disable Web Push** or **Disconnect** for Telegram. Your alert rules remain saved — you can re-enable delivery later without reconfiguring everything.

---

## Account Management

**Sign out:** Open **Settings** and tap **Sign Out**. This clears your session and returns you to the login page. Sessions persist for 30 days — you can close the browser and come back without re-entering your password.

**Forgot password:** On the sign-in page, tap **Forgot password** and follow the email instructions.
