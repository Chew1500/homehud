"""Dashboard UI package — composes tab modules into complete HTML."""

from telemetry.ui.config_tab import TAB_HTML as CONFIG_HTML
from telemetry.ui.config_tab import TAB_JS as CONFIG_JS
from telemetry.ui.garden import TAB_HTML as GARDEN_HTML
from telemetry.ui.garden import TAB_JS as GARDEN_JS
from telemetry.ui.grocery import TAB_HTML as GROCERY_HTML
from telemetry.ui.grocery import TAB_JS as GROCERY_JS
from telemetry.ui.logs import TAB_HTML as LOGS_HTML
from telemetry.ui.logs import TAB_JS as LOGS_JS
from telemetry.ui.overview import TAB_HTML as OVERVIEW_HTML
from telemetry.ui.overview import TAB_JS as OVERVIEW_JS
from telemetry.ui.recipes import TAB_HTML as RECIPES_HTML
from telemetry.ui.recipes import TAB_JS as RECIPES_JS
from telemetry.ui.services import TAB_HTML as SERVICES_HTML
from telemetry.ui.services import TAB_JS as SERVICES_JS
from telemetry.ui.sessions import TAB_HTML as SESSIONS_HTML
from telemetry.ui.sessions import TAB_JS as SESSIONS_JS
from telemetry.ui.shell import COMMON_JS, TAB_BAR, TAB_NAV_JS
from telemetry.ui.styles import DASHBOARD_STYLES
from telemetry.ui.voice_cache import TAB_HTML as VC_HTML
from telemetry.ui.voice_cache import TAB_JS as VC_JS
from telemetry.ui.voice_tab import TAB_HTML as VOICE_HTML
from telemetry.ui.voice_tab import TAB_JS as VOICE_JS


def build_dashboard_html() -> str:
    """Compose the complete dashboard HTML from all UI modules."""
    tabs_html = (
        OVERVIEW_HTML
        + SESSIONS_HTML
        + LOGS_HTML
        + CONFIG_HTML
        + VC_HTML
        + SERVICES_HTML
        + GARDEN_HTML
        + RECIPES_HTML
        + GROCERY_HTML
        + VOICE_HTML
    )
    tabs_js = (
        OVERVIEW_JS
        + SESSIONS_JS
        + LOGS_JS
        + CONFIG_JS
        + VC_JS
        + SERVICES_JS
        + GARDEN_JS
        + RECIPES_JS
        + GROCERY_JS
        + VOICE_JS
    )

    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1.0, maximum-scale=1.0, user-scalable=no">\n'
        '<title>Home HUD Telemetry</title>\n'
        '<meta name="theme-color" content="#3b82f6">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" '
        'content="black-translucent">\n'
        '<link rel="manifest" href="/manifest.json">\n'
        '<link rel="apple-touch-icon" href="/icons/192.png">\n'
        "<style>\n"
        + DASHBOARD_STYLES
        + "</style>\n</head>\n<body>\n"
        # Login screen (hidden by default, shown by JS when auth required)
        '<div id="hud-login" style="display:none">\n'
        '  <div style="max-width:360px;margin:0 auto;text-align:center;'
        'min-height:100vh;min-height:100dvh;display:flex;'
        'flex-direction:column;justify-content:center;padding:2rem 1rem">\n'
        '    <h1>Home HUD</h1>\n'
        '    <p style="color:#888;margin:1rem 0 2rem">'
        'Enter pairing code to connect</p>\n'
        '    <input id="pair-code-input" type="text" maxlength="6"'
        ' placeholder="000000"\n'
        '      style="font-size:2rem;text-align:center;width:200px;'
        'padding:0.5rem;\n'
        '      border:2px solid #ddd;border-radius:8px;'
        'font-family:SF Mono,Monaco,monospace"\n'
        '      onkeydown="if(event.key===\'Enter\')submitPairingCode()">\n'
        '    <br>\n'
        '    <button onclick="submitPairingCode()"\n'
        '      style="margin-top:1rem;padding:0.6rem 2rem;'
        'background:#3b82f6;\n'
        '      color:#fff;border:none;border-radius:6px;font-size:1rem;'
        'cursor:pointer;\n'
        '      font-weight:600">Connect</button>\n'
        '    <div id="pair-error" class="error-msg"'
        ' style="display:none;margin-top:1rem"></div>\n'
        '    <div style="margin-top:2rem;text-align:left;'
        'font-size:0.8rem;color:#888;line-height:1.6">\n'
        '      <p><strong>How to get a pairing code:</strong></p>\n'
        '      <p>Ask Home HUD: "generate pairing code"</p>\n'
        '      <p style="margin-top:1rem">'
        '<strong>Remote access via Tailscale:</strong></p>\n'
        '      <ol style="padding-left:1.2rem">\n'
        '        <li>Install Tailscale on your phone '
        '(iOS App Store / Google Play)</li>\n'
        '        <li>Sign in with the same account as the Pi</li>\n'
        '        <li>Access the dashboard via the Tailscale URL</li>\n'
        '        <li>Tailscale users are auto-authenticated</li>\n'
        '      </ol>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n\n'
        # Main content wrapper
        '<div id="hud-main">\n'
        '<div class="hud-header" id="hud-header">\n'
        '  <h1>Home HUD</h1>\n'
        '</div>\n\n'
        + TAB_BAR
        + "\n"
        + tabs_html
        + "\n</div>\n"
        + "\n<script>\n"
        + COMMON_JS
        + "\n"
        + tabs_js
        + "\n"
        + TAB_NAV_JS
        + "\n"
        "// Service worker registration\n"
        "if ('serviceWorker' in navigator) {\n"
        "  navigator.serviceWorker.register('/sw.js')\n"
        "    .catch(err => console.warn('SW registration failed:', err));\n"
        "}\n"
        "\n</script>\n</body>\n</html>\n"
    )
