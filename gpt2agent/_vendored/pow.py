# Ported from lanqian528/chat2api (MIT License)
# Copyright (c) 2024 aurora-develop
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# Source: https://github.com/lanqian528/chat2api  See NOTICES.md for full attribution.

from __future__ import annotations

import base64
import hashlib
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

_cores = [8, 16, 24, 32]
_time_layout = "%a %b %d %Y %H:%M:%S"

navigator_key = [
    "registerProtocolHandler−function registerProtocolHandler() { [native code] }",
    "storage−[object StorageManager]",
    "locks−[object LockManager]",
    "appCodeName−Mozilla",
    "permissions−[object Permissions]",
    "share−function share() { [native code] }",
    "webdriver−false",
    "managed−[object NavigatorManagedData]",
    "canShare−function canShare() { [native code] }",
    "vendor−Google Inc.",
    "vendor−Google Inc.",
    "mediaDevices−[object MediaDevices]",
    "vibrate−function vibrate() { [native code] }",
    "storageBuckets−[object StorageBucketManager]",
    "mediaCapabilities−[object MediaCapabilities]",
    "getGamepads−function getGamepads() { [native code] }",
    "bluetooth−[object Bluetooth]",
    "share−function share() { [native code] }",
    "cookieEnabled−true",
    "virtualKeyboard−[object VirtualKeyboard]",
    "product−Gecko",
    "mediaDevices−[object MediaDevices]",
    "canShare−function canShare() { [native code] }",
    "getGamepads−function getGamepads() { [native code] }",
    "product−Gecko",
    "xr−[object XRSystem]",
    "clipboard−[object Clipboard]",
    "storageBuckets−[object StorageBucketManager]",
    "unregisterProtocolHandler−function unregisterProtocolHandler() { [native code] }",
    "productSub−20030107",
    "login−[object NavigatorLogin]",
    "vendorSub−",
    "login−[object NavigatorLogin]",
    "getInstalledRelatedApps−function getInstalledRelatedApps() { [native code] }",
    "mediaDevices−[object MediaDevices]",
    "locks−[object LockManager]",
    "webkitGetUserMedia−function webkitGetUserMedia() { [native code] }",
    "vendor−Google Inc.",
    "xr−[object XRSystem]",
    "mediaDevices−[object MediaDevices]",
    "virtualKeyboard−[object VirtualKeyboard]",
    "virtualKeyboard−[object VirtualKeyboard]",
    "appName−Netscape",
    "storageBuckets−[object StorageBucketManager]",
    "presentation−[object Presentation]",
    "onLine−true",
    "mimeTypes−[object MimeTypeArray]",
    "credentials−[object CredentialsContainer]",
    "presentation−[object Presentation]",
    "getGamepads−function getGamepads() { [native code] }",
    "vendorSub−",
    "virtualKeyboard−[object VirtualKeyboard]",
    "serviceWorker−[object ServiceWorkerContainer]",
    "xr−[object XRSystem]",
    "product−Gecko",
    "keyboard−[object Keyboard]",
    "gpu−[object GPU]",
    "getInstalledRelatedApps−function getInstalledRelatedApps() { [native code] }",
    "webkitPersistentStorage−[object DeprecatedStorageQuota]",
    "doNotTrack",
    "clearAppBadge−function clearAppBadge() { [native code] }",
    "presentation−[object Presentation]",
    "serial−[object Serial]",
    "locks−[object LockManager]",
    "requestMIDIAccess−function requestMIDIAccess() { [native code] }",
    "locks−[object LockManager]",
    "requestMediaKeySystemAccess−function requestMediaKeySystemAccess() { [native code] }",
    "vendor−Google Inc.",
    "pdfViewerEnabled−true",
    # Must match the OAI-Language header set by BackendClient — Cloudflare's
    # bot manager cross-checks the navigator-fingerprint against the request
    # header and 403s on mismatch. Was zh-CN inherited from upstream chat2api;
    # we send en-US, so use en-US here too.
    "language−en-US",
    "setAppBadge−function setAppBadge() { [native code] }",
    "geolocation−[object Geolocation]",
    "userAgentData−[object NavigatorUAData]",
    "mediaCapabilities−[object MediaCapabilities]",
    "requestMIDIAccess−function requestMIDIAccess() { [native code] }",
    "getUserMedia−function getUserMedia() { [native code] }",
    "mediaDevices−[object MediaDevices]",
    "webkitPersistentStorage−[object DeprecatedStorageQuota]",
    "sendBeacon−function sendBeacon() { [native code] }",
    "hardwareConcurrency−32",
    "credentials−[object CredentialsContainer]",
    "storage−[object StorageManager]",
    "cookieEnabled−true",
    "pdfViewerEnabled−true",
    "windowControlsOverlay−[object WindowControlsOverlay]",
    "scheduling−[object Scheduling]",
    "pdfViewerEnabled−true",
    "hardwareConcurrency−32",
    "xr−[object XRSystem]",
    "webdriver−false",
    "getInstalledRelatedApps−function getInstalledRelatedApps() { [native code] }",
    "getInstalledRelatedApps−function getInstalledRelatedApps() { [native code] }",
    "bluetooth−[object Bluetooth]",
]

document_key = ["_reactListeningo743lnnpvdg", "location"]

window_key = [
    "0",
    "window",
    "self",
    "document",
    "name",
    "location",
    "customElements",
    "history",
    "navigation",
    "locationbar",
    "menubar",
    "personalbar",
    "scrollbars",
    "statusbar",
    "toolbar",
    "status",
    "closed",
    "frames",
    "length",
    "top",
    "opener",
    "parent",
    "frameElement",
    "navigator",
    "origin",
    "external",
    "screen",
    "innerWidth",
    "innerHeight",
    "scrollX",
    "pageXOffset",
    "scrollY",
    "pageYOffset",
    "visualViewport",
    "screenX",
    "screenY",
    "outerWidth",
    "outerHeight",
    "devicePixelRatio",
    "clientInformation",
    "screenLeft",
    "screenTop",
    "styleMedia",
    "onsearch",
    "isSecureContext",
    "trustedTypes",
    "performance",
    "onappinstalled",
    "onbeforeinstallprompt",
    "crypto",
    "indexedDB",
    "sessionStorage",
    "localStorage",
    "onbeforexrselect",
    "onabort",
    "onbeforeinput",
    "onbeforematch",
    "onbeforetoggle",
    "onblur",
    "oncancel",
    "oncanplay",
    "oncanplaythrough",
    "onchange",
    "onclick",
    "onclose",
    "oncontentvisibilityautostatechange",
    "oncontextlost",
    "oncontextmenu",
    "oncontextrestored",
    "oncuechange",
    "ondblclick",
    "ondrag",
    "ondragend",
    "ondragenter",
    "ondragleave",
    "ondragover",
    "ondragstart",
    "ondrop",
    "ondurationchange",
    "onemptied",
    "onended",
    "onerror",
    "onfocus",
    "onformdata",
    "oninput",
    "oninvalid",
    "onkeydown",
    "onkeypress",
    "onkeyup",
    "onload",
    "onloadeddata",
    "onloadedmetadata",
    "onloadstart",
    "onmousedown",
    "onmouseenter",
    "onmouseleave",
    "onmousemove",
    "onmouseout",
    "onmouseover",
    "onmouseup",
    "onmousewheel",
    "onpause",
    "onplay",
    "onplaying",
    "onprogress",
    "onratechange",
    "onreset",
    "onresize",
    "onscroll",
    "onsecuritypolicyviolation",
    "onseeked",
    "onseeking",
    "onselect",
    "onslotchange",
    "onstalled",
    "onsubmit",
    "onsuspend",
    "ontimeupdate",
    "ontoggle",
    "onvolumechange",
    "onwaiting",
    "onwebkitanimationend",
    "onwebkitanimationiteration",
    "onwebkitanimationstart",
    "onwebkittransitionend",
    "onwheel",
    "onauxclick",
    "ongotpointercapture",
    "onlostpointercapture",
    "onpointerdown",
    "onpointermove",
    "onpointerrawupdate",
    "onpointerup",
    "onpointercancel",
    "onpointerover",
    "onpointerout",
    "onpointerenter",
    "onpointerleave",
    "onselectstart",
    "onselectionchange",
    "onanimationend",
    "onanimationiteration",
    "onanimationstart",
    "ontransitionrun",
    "ontransitionstart",
    "ontransitionend",
    "ontransitioncancel",
    "onafterprint",
    "onbeforeprint",
    "onbeforeunload",
    "onhashchange",
    "onlanguagechange",
    "onmessage",
    "onmessageerror",
    "onoffline",
    "ononline",
    "onpagehide",
    "onpageshow",
    "onpopstate",
    "onrejectionhandled",
    "onstorage",
    "onunhandledrejection",
    "onunload",
    "crossOriginIsolated",
    "scheduler",
    "alert",
    "atob",
    "blur",
    "btoa",
    "cancelAnimationFrame",
    "cancelIdleCallback",
    "captureEvents",
    "clearInterval",
    "clearTimeout",
    "close",
    "confirm",
    "createImageBitmap",
    "fetch",
    "find",
    "focus",
    "getComputedStyle",
    "getSelection",
    "matchMedia",
    "moveBy",
    "moveTo",
    "open",
    "postMessage",
    "print",
    "prompt",
    "queueMicrotask",
    "releaseEvents",
    "reportError",
    "requestAnimationFrame",
    "requestIdleCallback",
    "resizeBy",
    "resizeTo",
    "scroll",
    "scrollBy",
    "scrollTo",
    "setInterval",
    "setTimeout",
    "stop",
    "structuredClone",
    "webkitCancelAnimationFrame",
    "webkitRequestAnimationFrame",
    "chrome",
    "caches",
    "cookieStore",
    "ondevicemotion",
    "ondeviceorientation",
    "ondeviceorientationabsolute",
    "launchQueue",
    "documentPictureInPicture",
    "getScreenDetails",
    "queryLocalFonts",
    "showDirectoryPicker",
    "showOpenFilePicker",
    "showSaveFilePicker",
    "originAgentCluster",
    "onpageswap",
    "onpagereveal",
    "credentialless",
    "speechSynthesis",
    "onscrollend",
    "webkitRequestFileSystem",
    "webkitResolveLocalFileSystemURL",
    "sendMsgToSolverCS",
    "webpackChunk_N_E",
    "__next_set_public_path__",
    "next",
    "__NEXT_DATA__",
    "__SSG_MANIFEST_CB",
    "__NEXT_P",
    "_N_E",
    "regeneratorRuntime",
    "__REACT_INTL_CONTEXT__",
    "DD_RUM",
    "_",
    "filterCSS",
    "filterXSS",
    "__SEGMENT_INSPECTOR__",
    "__NEXT_PRELOADREADY",
    "Intercom",
    "__MIDDLEWARE_MATCHERS",
    "__STATSIG_SDK__",
    "__STATSIG_JS_SDK__",
    "__STATSIG_RERENDER_OVERRIDE__",
    "_oaiHandleSessionExpired",
    "__BUILD_MANIFEST",
    "__SSG_MANIFEST",
    "__intercomAssignLocation",
    "__intercomReloadLocation",
]


def _parse_time() -> str:
    now = datetime.now(timezone(timedelta(hours=-5)))
    return now.strftime(_time_layout) + " GMT-0500 (Eastern Standard Time)"


def build_config(user_agent: str, dpl: str = "", script_src: str = "") -> list:
    return [
        random.choice([1920 + 1080, 2560 + 1440, 1920 + 1200, 2560 + 1600]),
        _parse_time(),
        4294705152,
        0,
        user_agent,
        script_src,
        dpl,
        "en-US",
        "en-US,es-US,en,es",
        0,
        random.choice(navigator_key),
        random.choice(document_key),
        random.choice(window_key),
        time.perf_counter() * 1000,
        str(uuid.uuid4()),
        "",
        random.choice(_cores),
        time.time() * 1000 - (time.perf_counter() * 1000),
    ]


def _generate_answer(seed: str, diff: str, config: list) -> tuple[str, bool]:
    diff_len = len(diff)
    seed_encoded = seed.encode()
    part1 = (
        json.dumps(config[:3], separators=(",", ":"), ensure_ascii=False)[:-1] + ","
    ).encode()
    part2 = (
        ","
        + json.dumps(config[4:9], separators=(",", ":"), ensure_ascii=False)[1:-1]
        + ","
    ).encode()
    part3 = (
        "," + json.dumps(config[10:], separators=(",", ":"), ensure_ascii=False)[1:]
    ).encode()
    target = bytes.fromhex(diff)

    for i in range(500000):
        dyn_i = str(i).encode()
        dyn_j = str(i >> 1).encode()
        final_bytes = part1 + dyn_i + part2 + dyn_j + part3
        base_encoded = base64.b64encode(final_bytes)
        h = hashlib.sha3_512(seed_encoded + base_encoded).digest()
        if h[:diff_len] <= target:
            return base_encoded.decode(), True

    return (
        "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D"
        + base64.b64encode(f'"{seed}"'.encode()).decode(),
        False,
    )


def solve_pow(seed: str, difficulty: str, user_agent: str) -> str:
    config = build_config(user_agent)
    answer, _solved = _generate_answer(seed, difficulty, config)
    if not _solved:
        import logging

        logging.getLogger(__name__).warning(
            "POW solver did not find an answer within the iteration budget — "
            "falling back to stub token; request may be challenged."
        )
    return "gAAAAAB" + answer


def get_requirements_token(user_agent: str) -> str:
    config = build_config(user_agent)
    require, _ = _generate_answer(format(random.random()), "0fffff", config)
    return "gAAAAAC" + require
