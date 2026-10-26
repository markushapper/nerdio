package com.markushapper.nerdio;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

public class MainActivity extends Activity {
    private static final String APP_URL = "https://markushapper.github.io/song-reveal/?native=1";
    private static final String APP_HOST = "markushapper.github.io";
    private static final String APP_PATH = "/song-reveal/";
    private static final String AMAZON_PACKAGE = "com.amazon.mp3";
    private static final int FILE_CHOOSER_REQUEST = 7001;
    private static final long AMAZON_HANDOFF_MS = 700L;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private FrameLayout activityHost;
    private WebView webView;
    private WindowManager overlayWindowManager;
    private boolean overlayAttached = false;
    private ValueCallback<Uri[]> filePathCallback;
    private Runnable pauseRunnable;
    private Runnable returnRunnable;
    private PowerManager.WakeLock wakeLock;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        activityHost = new FrameLayout(this);
        activityHost.setBackgroundColor(Color.rgb(9, 11, 22));
        setContentView(activityHost);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(9, 11, 22));
        activityHost.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        configureWebView();
        if (savedInstanceState == null) {
            webView.loadUrl(APP_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " NerdioAndroid/2.0");

        webView.addJavascriptInterface(new NerdioBridge(), "NerdioNative");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleNavigation(request.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                view.evaluateJavascript(
                        "document.body.classList.add('native-mode');" +
                        "window.dispatchEvent(new Event('nerdio-native-ready'));",
                        null);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;
                Intent intent;
                try {
                    intent = params.createIntent();
                } catch (ActivityNotFoundException ex) {
                    filePathCallback = null;
                    return false;
                }
                startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                return true;
            }
        });
    }

    private boolean handleNavigation(Uri uri) {
        String scheme = uri.getScheme();
        String host = uri.getHost();
        String path = uri.getPath();
        if ("https".equalsIgnoreCase(scheme)
                && APP_HOST.equalsIgnoreCase(host)
                && path != null
                && path.startsWith(APP_PATH)) {
            return false;
        }

        Intent external = new Intent(Intent.ACTION_VIEW, uri);
        try {
            startActivity(external);
        } catch (ActivityNotFoundException ignored) {
        }
        return true;
    }

    private void startTimedPlayback(String rawUrl, int requestedSeconds) {
        int seconds = Math.max(3, Math.min(60, requestedSeconds));
        Uri uri;
        try {
            uri = Uri.parse(rawUrl);
        } catch (Exception ex) {
            notifyNativeError("Ungültiger Amazon-Link");
            return;
        }
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                || !uri.getHost().toLowerCase().contains("amazon.")) {
            notifyNativeError("Nur Amazon-Music-Links sind erlaubt");
            return;
        }

        if (!Settings.canDrawOverlays(this)) {
            requestOverlayPermission();
            notifyNativeError("Bitte „Über anderen Apps anzeigen“ erlauben und Song erneut starten.");
            return;
        }

        cancelScheduledPlayback(false);
        if (!attachNerdioOverlay()) {
            notifyNativeError("Nerdio-Overlay konnte nicht gestartet werden.");
            return;
        }

        acquireWakeLock((seconds * 1000L) + AMAZON_HANDOFF_MS + 5000L);

        Intent amazon = new Intent(Intent.ACTION_VIEW, uri);
        amazon.setPackage(AMAZON_PACKAGE);
        try {
            startActivity(amazon);
        } catch (ActivityNotFoundException ex) {
            Intent fallback = new Intent(Intent.ACTION_VIEW, uri);
            try {
                startActivity(fallback);
            } catch (ActivityNotFoundException ignored) {
                releaseWakeLock();
                notifyNativeError("Amazon Music konnte nicht geöffnet werden");
                return;
            }
        }

        returnRunnable = () -> {
            bringNerdioToFront();
            notifyPlaybackStarted(seconds);
        };
        handler.postDelayed(returnRunnable, AMAZON_HANDOFF_MS);

        pauseRunnable = () -> {
            pauseCurrentMedia();
            notifyPlaybackPaused();
            releaseWakeLock();
            pauseRunnable = null;
        };
        handler.postDelayed(pauseRunnable, AMAZON_HANDOFF_MS + seconds * 1000L);
    }

    private void bringNerdioToFront() {
        try {
            ActivityManager manager = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
            manager.moveTaskToFront(getTaskId(), ActivityManager.MOVE_TASK_WITH_HOME);
        } catch (Exception ex) {
            try {
                Intent self = new Intent(this, MainActivity.class);
                self.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                startActivity(self);
            } catch (Exception ignored) {
            }
        }
        returnRunnable = null;
    }

    private void requestOverlayPermission() {
        try {
            Intent intent = new Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } catch (ActivityNotFoundException ex) {
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION));
            } catch (ActivityNotFoundException ignored) {
            }
        }
    }

    private boolean attachNerdioOverlay() {
        if (overlayAttached) return true;
        if (!Settings.canDrawOverlays(this)) return false;

        try {
            ViewGroup parent = (ViewGroup) webView.getParent();
            if (parent != null) parent.removeView(webView);

            overlayWindowManager = (WindowManager) getApplicationContext()
                    .getSystemService(Context.WINDOW_SERVICE);

            WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                    WindowManager.LayoutParams.MATCH_PARENT,
                    WindowManager.LayoutParams.MATCH_PARENT,
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                    PixelFormat.OPAQUE);
            params.gravity = Gravity.TOP | Gravity.START;
            params.setTitle("Nerdio");

            overlayWindowManager.addView(webView, params);
            overlayAttached = true;
            return true;
        } catch (Exception ex) {
            overlayAttached = false;
            try {
                if (webView.getParent() == null) {
                    activityHost.addView(webView, new FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT));
                }
            } catch (Exception ignored) {
            }
            return false;
        }
    }

    private void detachNerdioOverlay() {
        if (!overlayAttached) return;
        try {
            if (overlayWindowManager != null) {
                overlayWindowManager.removeViewImmediate(webView);
            }
        } catch (Exception ignored) {
        }
        overlayAttached = false;
        overlayWindowManager = null;

        try {
            ViewGroup parent = (ViewGroup) webView.getParent();
            if (parent != null) parent.removeView(webView);
            if (webView.getParent() == null) {
                activityHost.addView(webView, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT));
            }
        } catch (Exception ignored) {
        }
    }

    private void pauseCurrentMedia() {
        AudioManager audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        long now = SystemClock.uptimeMillis();
        audioManager.dispatchMediaKeyEvent(new KeyEvent(
                now, now, KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PAUSE, 0));
        audioManager.dispatchMediaKeyEvent(new KeyEvent(
                now, now, KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_PAUSE, 0));
    }

    private void pauseNow() {
        handler.post(() -> {
            cancelScheduledPlayback(false);
            pauseCurrentMedia();
            notifyPlaybackPaused();
            releaseWakeLock();
        });
    }

    private void cancelScheduledPlayback(boolean releaseLock) {
        if (pauseRunnable != null) {
            handler.removeCallbacks(pauseRunnable);
            pauseRunnable = null;
        }
        if (returnRunnable != null) {
            handler.removeCallbacks(returnRunnable);
            returnRunnable = null;
        }
        if (releaseLock) releaseWakeLock();
    }

    private void acquireWakeLock(long timeoutMs) {
        releaseWakeLock();
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Nerdio:SongTimer");
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire(timeoutMs);
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        wakeLock = null;
    }

    private void notifyPlaybackStarted(int seconds) {
        runOnUiThread(() -> webView.evaluateJavascript(
                "window.NerdioNativeCallbacks && window.NerdioNativeCallbacks.onPlaybackStarted && window.NerdioNativeCallbacks.onPlaybackStarted(" + seconds + ")",
                null));
    }

    private void notifyPlaybackPaused() {
        runOnUiThread(() -> webView.evaluateJavascript(
                "window.NerdioNativeCallbacks && window.NerdioNativeCallbacks.onPlaybackPaused && window.NerdioNativeCallbacks.onPlaybackPaused()",
                null));
    }

    private void notifyNativeError(String message) {
        final String safe = message.replace("\\", "\\\\").replace("'", "\\'");
        runOnUiThread(() -> webView.evaluateJavascript(
                "window.NerdioNativeCallbacks && window.NerdioNativeCallbacks.onError && window.NerdioNativeCallbacks.onError('" + safe + "')",
                null));
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (overlayAttached) {
            detachNerdioOverlay();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        if (!overlayAttached) webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (overlayAttached) {
            if (webView.canGoBack()) webView.goBack();
            return;
        }
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        cancelScheduledPlayback(true);
        detachNerdioOverlay();
        if (webView != null) webView.destroy();
        super.onDestroy();
    }

    public final class NerdioBridge {
        @JavascriptInterface
        public void playSong(String url, int seconds) {
            runOnUiThread(() -> startTimedPlayback(url, seconds));
        }

        @JavascriptInterface
        public void pauseNow() {
            MainActivity.this.pauseNow();
        }

        @JavascriptInterface
        public boolean hasOverlayPermission() {
            return Settings.canDrawOverlays(MainActivity.this);
        }

        @JavascriptInterface
        public void requestOverlayPermission() {
            runOnUiThread(MainActivity.this::requestOverlayPermission);
        }

        @JavascriptInterface
        public boolean isNative() {
            return true;
        }
    }
}
