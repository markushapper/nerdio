package com.markushapper.nerdio;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewTreeObserver;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.FrameLayout;

public class NerdioAccessibilityService extends AccessibilityService {
    private static NerdioAccessibilityService instance;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private WindowManager windowManager;
    private View coverView;

    public static boolean isConnected() {
        return instance != null;
    }

    public static boolean showPlaybackCover(Runnable onFirstDraw) {
        NerdioAccessibilityService service = instance;
        if (service == null) return false;
        service.handler.post(() -> service.showCoverInternal(onFirstDraw));
        return true;
    }

    public static void hidePlaybackCover() {
        NerdioAccessibilityService service = instance;
        if (service == null) return;
        service.handler.post(service::hideCoverInternal);
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // No accessibility data is inspected. The service only owns the trusted cover window.
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public void onDestroy() {
        hideCoverInternal();
        if (instance == this) instance = null;
        super.onDestroy();
    }

    private void showCoverInternal(Runnable onFirstDraw) {
        if (coverView != null) {
            if (onFirstDraw != null) handler.post(onFirstDraw);
            return;
        }
        if (windowManager == null) {
            windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        }
        if (windowManager == null) return;

        FrameLayout cover = new FrameLayout(this);
        cover.setBackgroundColor(Color.rgb(9, 11, 22));
        cover.setAlpha(1f);

        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                PixelFormat.OPAQUE);
        params.gravity = Gravity.TOP | Gravity.START;
        params.setTitle("Nerdio playback cover");

        final ViewTreeObserver.OnDrawListener[] listener =
                new ViewTreeObserver.OnDrawListener[1];
        listener[0] = () -> cover.post(() -> {
            ViewTreeObserver observer = cover.getViewTreeObserver();
            if (observer.isAlive()) {
                observer.removeOnDrawListener(listener[0]);
            }
            if (coverView == cover && onFirstDraw != null) {
                onFirstDraw.run();
            }
        });
        cover.getViewTreeObserver().addOnDrawListener(listener[0]);

        try {
            windowManager.addView(cover, params);
            coverView = cover;
        } catch (Exception ignored) {
            coverView = null;
        }
    }

    private void hideCoverInternal() {
        if (coverView == null || windowManager == null) return;
        try {
            windowManager.removeViewImmediate(coverView);
        } catch (Exception ignored) {
        }
        coverView = null;
    }
}
