package app.mamia.android

import android.Manifest
import android.annotation.SuppressLint
import android.app.DownloadManager
import android.app.NotificationManager
import android.content.Intent
import android.graphics.Color as AColor
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.webkit.CookieManager
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowInsetsControllerCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/** The Mam-IA app: the server's web app full screen (the same one as in the browser, so every change on the server
 *  shows here at once), with what a web page cannot do by itself — reminders at their exact time, "Share with Mam-IA",
 *  downloads, choosing files, the back button, the system edges and a start screen. */
class MainActivity : ComponentActivity() {
    private lateinit var prefs: Prefs
    private var web: WebView? = null
    private val page = mutableStateOf(Page.LOADING)
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    /** A page to open once the web app is there (a shared text, a notification, a link): a path or a full address. */
    private var pending: String? = null
    private lateinit var bridge: NativeBridge

    private enum class Page { SETUP, LOADING, READY, ERROR }

    private val pickFiles = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        fileCallback?.onReceiveValue(uris.toTypedArray()); fileCallback = null
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        askExactAlarms()
        tellNotifications()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        prefs = Prefs(this)
        bridge = NativeBridge(this)
        Notifier.ensureChannel(this)
        if (prefs.server.isEmpty()) page.value = Page.SETUP
        // the start screen stays until the page has loaded (or failed, or the server has to be set)
        val t0 = System.currentTimeMillis()
        splash.setKeepOnScreenCondition { page.value == Page.LOADING && System.currentTimeMillis() - t0 < 8000 }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = goBack()
        })
        handleIntent(intent)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFFC93E66))) {
                when (page.value) {
                    Page.SETUP -> Surface(Modifier.fillMaxSize(), color = Color(0xFFF6F3F6)) { ServerSetup(prefs.server) { saveServer(it) } }
                    else -> Box(Modifier.fillMaxSize().background(Color(barColor)).safeDrawingPadding()) {
                        AndroidView(factory = { web ?: makeWebView().also { web = it } }, modifier = Modifier.fillMaxSize())
                        if (page.value == Page.ERROR) Surface(Modifier.fillMaxSize(), color = Color(0xFFF6F3F6)) {
                            Offline({ reload() }, { changeServer() })
                        }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        tellNotifications()   // back from Android's settings: the page learns whether reminders can ring now
    }

    override fun onPause() {
        super.onPause()
        CookieManager.getInstance().flush()
    }

    private var barColor by mutableStateOf(0xFFF6F3F6.toInt())

    /** Shared text, a link to the server or a notification (its page, or "Done"): opened in the web app. */
    private fun handleIntent(intent: Intent?) {
        intent ?: return
        val nid = intent.getIntExtra(Notifier.EXTRA_NOTIFICATION, 0)
        if (nid != 0) getSystemService(NotificationManager::class.java)?.cancel(nid)
        val target = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(intent.getStringExtra(Intent.EXTRA_SUBJECT), intent.getStringExtra(Intent.EXTRA_TEXT))
                .joinToString("\n").trim().takeIf { it.isNotEmpty() }?.let { "/app?apuntar=" + Uri.encode(it.take(2000)) }
            Intent.ACTION_VIEW -> intent.data?.takeIf { (it.scheme == "https" || it.scheme == "http") }?.toString()
            else -> null
        } ?: return
        open(target)
    }

    private fun open(target: String) {
        val w = web
        if (w == null || page.value == Page.SETUP) { pending = target; return }
        resolve(target)?.let { page.value = Page.LOADING; w.loadUrl(it) }
    }

    /** A path of the server, or a full address of the same server; null for anything else. */
    private fun resolve(target: String): String? = when {
        prefs.server.isEmpty() -> null
        target.startsWith("/") -> prefs.server + target
        sameServer(Uri.parse(target)) -> target
        else -> null
    }

    private fun sameServer(u: Uri): Boolean = prefs.server.isNotEmpty() && Uri.parse(prefs.server).host == u.host

    @SuppressLint("SetJavaScriptEnabled")
    private fun makeWebView(): WebView = WebView(this).apply {
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.mediaPlaybackRequiresUserGesture = true
        settings.allowFileAccess = false
        settings.userAgentString = settings.userAgentString + " MamIAApp/" + appVersion()
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
        addJavascriptInterface(bridge, "MamIANative")
        webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                request.isForMainFrame && route(request.url)

            override fun onPageFinished(view: WebView, url: String) {
                if (page.value != Page.ERROR) page.value = Page.READY
                // the bars around the page take the page's background colour (its theme)
                view.evaluateJavascript("getComputedStyle(document.body).backgroundColor") { c -> applyBarColor(c) }
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) page.value = Page.ERROR
            }

            override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, response: WebResourceResponse) {
                if (request.isForMainFrame && response.statusCode >= 500) page.value = Page.ERROR
            }
        }
        webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                var types = params.acceptTypes.filter { it.contains('/') }.ifEmpty { listOf("*/*") }
                if (types.any { "json" in it }) types = listOf("*/*")   // many file apps report a backup as octet-stream
                return try { pickFiles.launch(types.toTypedArray()); true } catch (_: Exception) { fileCallback = null; false }
            }
        }
        // files the server sends for download (the page's own files go through NativeBridge.saveFile)
        setDownloadListener { url, ua, disposition, mime, _ ->
            if (!url.startsWith("http")) return@setDownloadListener
            val name = URLUtil.guessFileName(url, disposition, mime)
            val req = DownloadManager.Request(Uri.parse(url))
                .addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url) ?: "")
                .addRequestHeader("User-Agent", ua)
                .setMimeType(mime)
                .setTitle(name)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name)
            (getSystemService(DOWNLOAD_SERVICE) as DownloadManager).enqueue(req)
        }
        val first = pending?.let { resolve(it) } ?: (prefs.server + "/app")
        pending = null
        loadUrl(first)
    }

    /** Pages of the server and Stripe's payment pages stay in the app; anything else (mail, phone, WhatsApp, other
     *  websites) opens outside. */
    private fun route(u: Uri): Boolean {
        val host = u.host ?: ""
        if ((u.scheme == "https" || u.scheme == "http") && (sameServer(u) || host in STRIPE_HOSTS)) return false
        try { startActivity(Intent(Intent.ACTION_VIEW, u)) } catch (_: Exception) { }
        return true
    }

    private fun applyBarColor(css: String?) {
        val m = Regex("""rgba?\((\d+),\s*(\d+),\s*(\d+)""").find(css ?: "") ?: return
        val (r, g, b) = m.destructured.toList().map { it.toInt() }
        barColor = AColor.rgb(r, g, b)
        val light = (r * 299 + g * 587 + b * 114) / 1000 > 140
        WindowInsetsControllerCompat(window, window.decorView).apply {
            isAppearanceLightStatusBars = light; isAppearanceLightNavigationBars = light
        }
    }

    /** Back: first what the page has open (a sheet, a menu…: window.mamiaBack()), then the previous screen, then leave. */
    private fun goBack() {
        val w = web
        if (w == null || page.value != Page.READY) { finish(); return }
        w.evaluateJavascript("(window.mamiaBack&&window.mamiaBack())?1:0") { r ->
            if (r == "1") return@evaluateJavascript
            if (w.canGoBack()) w.goBack() else finish()
        }
    }

    fun reload() {
        page.value = Page.LOADING
        web?.reload() ?: run { page.value = Page.READY }
    }

    /** Called by the page or the offline screen: go back to choosing the server. */
    fun changeServer() {
        prefs.server = ""
        web?.destroy(); web = null
        page.value = Page.SETUP
    }

    private fun saveServer(url: String) {
        prefs.server = url
        page.value = Page.LOADING   // the WebView is made (and loads the server, or the pending page) when it shows
    }

    /** Notifications (Android 13+) and then, if missing, exact alarms (Android 12+: their screen in the settings). */
    fun askNotifications() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        askExactAlarms()
        tellNotifications()
    }

    private fun askExactAlarms() {
        if (Build.VERSION.SDK_INT < 31 || Alarms.exactAllowed(this)) return
        try {
            startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:$packageName")))
        } catch (_: Exception) { }
    }

    private fun tellNotifications() {
        if (page.value != Page.READY) return
        js("window.dispatchEvent(new CustomEvent('mamia-notifications',{detail:{allowed:${Notifier.allowed(this)}," +
            "exact:${Alarms.exactAllowed(this)}}}))")
    }

    /** Runs a script in the page (on the UI thread). */
    fun js(script: String) = runOnUiThread { web?.evaluateJavascript(script, null) }

    fun appVersion(): String = try {
        packageManager.getPackageInfo(packageName, 0).versionName ?: "0"
    } catch (_: Exception) { "0" }

    @Composable
    private fun ServerSetup(current: String, onSave: (String) -> Unit) {
        var url by remember { mutableStateOf(current.ifEmpty { DEFAULT_SERVER }) }
        var busy by remember { mutableStateOf(false) }
        var err by remember { mutableStateOf("") }
        val scope = rememberCoroutineScope()
        val errText = stringResource(R.string.server_error)
        Column(Modifier.safeDrawingPadding().padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Mam-IA", fontSize = 32.sp, fontWeight = FontWeight.ExtraBold, color = Color(0xFF231B29))
            Text(stringResource(R.string.server_intro), color = Color(0xFF231B29))
            OutlinedTextField(value = url, onValueChange = { url = it; err = "" }, singleLine = true,
                label = { Text(stringResource(R.string.server_label)) }, modifier = Modifier.fillMaxWidth())
            if (err.isNotEmpty()) Text(err, color = MaterialTheme.colorScheme.error)
            Button(enabled = !busy, modifier = Modifier.fillMaxWidth(), onClick = {
                val u = normalise(url)
                busy = true
                scope.launch {
                    val ok = withContext(Dispatchers.IO) { reachable(u) }
                    busy = false
                    if (ok) onSave(u) else err = errText
                }
            }) { Text(stringResource(if (busy) R.string.server_checking else R.string.server_go)) }
            Text(stringResource(R.string.server_help), fontSize = 13.sp, color = Color(0xFF5F5568))
        }
    }

    @Composable
    private fun Offline(onRetry: () -> Unit, onChange: () -> Unit) {
        Column(Modifier.safeDrawingPadding().padding(24.dp).fillMaxSize(), verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Mam-IA", fontSize = 32.sp, fontWeight = FontWeight.ExtraBold, color = Color(0xFF231B29))
            Text(stringResource(R.string.offline), Modifier.padding(vertical = 16.dp), color = Color(0xFF231B29))
            Button(onClick = onRetry) { Text(stringResource(R.string.retry)) }
            TextButton(onClick = onChange) { Text(stringResource(R.string.change_server)) }
        }
    }

    companion object {
        /** Suggested server for a new installation (it can be changed). */
        const val DEFAULT_SERVER = "https://mamia.jtgcloud.com"
        /** Stripe's checkout and customer portal: the subscription is paid inside the app and comes back to it. */
        private val STRIPE_HOSTS = setOf("checkout.stripe.com", "billing.stripe.com")

        fun normalise(s: String): String {
            var u = s.trim().trimEnd('/')
            if (!u.startsWith("http://") && !u.startsWith("https://")) u = "https://$u"
            return u
        }

        fun reachable(base: String): Boolean = try {
            val c = URL("$base/healthz").openConnection() as HttpURLConnection
            c.connectTimeout = 10000; c.readTimeout = 10000
            val ok = c.responseCode == 200 && c.inputStream.bufferedReader().use { it.readText() }.contains("\"ok\"")
            c.disconnect(); ok
        } catch (_: Exception) { false }
    }
}
