package app.mamia.android

import android.content.Context

/** Settings of the app: the server's address and the reminders scheduled (to set them again after a restart). */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("mamia", Context.MODE_PRIVATE)

    /** Address of the Mam-IA server the app shows (https://…); empty until the first set-up. */
    var server: String
        get() = sp.getString("server", "") ?: ""
        set(v) = sp.edit().putString("server", v.trim().trimEnd('/')).apply()

    /** The reminders the web app gave last (JSON array, see [Alarm]). */
    var alarms: String
        get() = sp.getString("alarms", "[]") ?: "[]"
        set(v) = sp.edit().putString("alarms", v).apply()

    /** Reminders postponed from their notification: kept apart, so the web app's next list does not drop them. */
    var snoozed: String
        get() = sp.getString("snoozed", "[]") ?: "[]"
        set(v) = sp.edit().putString("snoozed", v).apply()
}
