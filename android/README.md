# Nerdio Android wrapper

Thin Android host around the existing Nerdio web app.

## Native playback flow

1. The WebView calls `NerdioNative.playSong(url, seconds)`.
2. Android opens the Amazon Music deep link.
3. After a short handoff (~700 ms), the existing Nerdio task is moved back to the foreground.
4. A partial wake lock keeps the short timer reliable if the screen is turned off.
5. When the configured timer expires, Android sends `KEYCODE_MEDIA_PAUSE` to the current media consumer. This does not navigate Amazon Music to the foreground.

The PWA remains usable in a normal browser; the native timer controls are only shown when `NerdioNative` is available.
