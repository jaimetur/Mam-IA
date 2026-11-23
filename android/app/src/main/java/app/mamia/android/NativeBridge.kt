package app.mamia.android

import android.content.ContentValues
import android.content.Intent
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File

/** What the web app can ask the Android app for (window.MamIANative in the page). The WebView only shows pages of the
 *  Mam-IA server, so only those pages can call it. Methods run on a background thread. */
class NativeBridge(private val activity: MainActivity) {

    /** The reminders of the coming days, as a JSON array of {id, at, title, body, path}: replaces the whole set. */
    @JavascriptInterface
    fun setAlarms(json: String) = Alarms.replace(activity.applicationContext, json)

    @JavascriptInterface
    fun notificationsAllowed(): Boolean = Notifier.allowed(activity)

    /** Reminders ring at their exact time (Android 12+ lets the user withdraw it). */
    @JavascriptInterface
    fun exactAlarmsAllowed(): Boolean = Alarms.exactAllowed(activity)

    /** Asks for the notifications and, if missing, the exact alarms; the page hears the result as the
     *  "mamia-notifications" event ({detail: {allowed, exact}}). */
    @JavascriptInterface
    fun askNotifications() = activity.runOnUiThread { activity.askNotifications() }

    @JavascriptInterface
    fun appVersion(): String = activity.appVersion()

    /** Back to choosing the server (from the account page). */
    @JavascriptInterface
    fun changeServer() = activity.runOnUiThread { activity.changeServer() }

    /** A file made by the page (the family's backup): saved in Downloads (Android 10+) or shared (Android 9). */
    @JavascriptInterface
    fun saveFile(name: String, mime: String, base64: String) {
        val clean = name.replace(Regex("[\\\\/:*?\"<>|]"), "_").ifBlank { "Mam-IA" }
        val bytes = try { Base64.decode(base64, Base64.DEFAULT) } catch (_: Exception) { return toast(activity.getString(R.string.save_failed)) }
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                val v = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, clean); put(MediaStore.Downloads.MIME_TYPE, mime)
                    put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }
                val uri = activity.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v)
                    ?: return toast(activity.getString(R.string.save_failed))
                activity.contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                toast(activity.getString(R.string.saved_downloads, clean))
            } else {
                val f = File(File(activity.cacheDir, "shared").apply { mkdirs() }, clean).apply { writeBytes(bytes) }
                val uri = FileProvider.getUriForFile(activity, activity.packageName + ".files", f)
                val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                activity.runOnUiThread { activity.startActivity(Intent.createChooser(send, clean)) }
            }
        } catch (e: Exception) {
            toast(e.message ?: activity.getString(R.string.save_failed))
        }
    }

    private fun toast(text: String) = activity.runOnUiThread { Toast.makeText(activity, text, Toast.LENGTH_LONG).show() }
}
