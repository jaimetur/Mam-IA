package app.mamia.android

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject

/** A reminder the web app asked for: [at] in Unix milliseconds, [path] the page of the server it opens ("/app#agenda"). */
data class Alarm(val id: String, val at: Long, val title: String, val body: String, val path: String) {
    fun json(): JSONObject = JSONObject().put("id", id).put("at", at).put("title", title).put("body", body).put("path", path)

    companion object {
        fun from(o: JSONObject?): Alarm? {
            val id = o?.optString("id").orEmpty().take(200)
            val title = o?.optString("title").orEmpty().take(200)
            if (o == null || id.isEmpty() || title.isEmpty()) return null
            val path = o.optString("path").takeIf { it.startsWith("/") && !it.startsWith("//") } ?: "/app"
            return Alarm(id, o.optLong("at"), title, o.optString("body").take(500), path.take(500))
        }

        fun from(s: String?): Alarm? = try { from(JSONObject(s ?: "")) } catch (_: Exception) { null }

        fun list(s: String?): List<Alarm> = try {
            val a = JSONArray(s ?: "[]")
            (0 until a.length()).mapNotNull { from(a.optJSONObject(it)) }
        } catch (_: Exception) { emptyList() }

        fun json(list: List<Alarm>): String = JSONArray().apply { list.forEach { put(it.json()) } }.toString()
    }
}

/** Schedules the reminders with AlarmManager, at their exact time when Android allows it. */
object Alarms {
    const val ACTION_FIRE = "app.mamia.android.ALARM"
    const val ACTION_SNOOZE = "app.mamia.android.SNOOZE"
    const val EXTRA_ALARM = "alarm"
    const val EXTRA_SNOOZED = "snoozed"
    private const val MAX = 200
    private const val SNOOZE_MS = 10 * 60_000L

    /** The web app's whole list: the new ones are scheduled, the ones no longer in it are cancelled. */
    @Synchronized
    fun replace(ctx: Context, json: String) {
        val prefs = Prefs(ctx)
        val now = System.currentTimeMillis()
        val next = Alarm.list(json).filter { it.at > now }.distinctBy { it.id }.sortedBy { it.at }.take(MAX)
        val ids = next.map { it.id }.toSet()
        Alarm.list(prefs.alarms).filter { it.id !in ids }.forEach { cancel(ctx, it.id, snoozed = false) }
        next.forEach { schedule(ctx, it, snoozed = false) }
        prefs.alarms = Alarm.json(next)
    }

    /** After a restart or an update of the app: every reminder still to come, again. */
    @Synchronized
    fun rescheduleAll(ctx: Context) {
        val prefs = Prefs(ctx)
        val now = System.currentTimeMillis()
        val main = Alarm.list(prefs.alarms).filter { it.at > now }
        val snoozed = Alarm.list(prefs.snoozed).filter { it.at > now }
        main.forEach { schedule(ctx, it, snoozed = false) }
        snoozed.forEach { schedule(ctx, it, snoozed = true) }
        prefs.alarms = Alarm.json(main)
        prefs.snoozed = Alarm.json(snoozed)
    }

    /** "Snooze 10 min" in the notification. */
    @Synchronized
    fun snooze(ctx: Context, alarm: Alarm) {
        val prefs = Prefs(ctx)
        val later = alarm.copy(at = System.currentTimeMillis() + SNOOZE_MS)
        prefs.snoozed = Alarm.json(Alarm.list(prefs.snoozed).filter { it.id != alarm.id } + later)
        schedule(ctx, later, snoozed = true)
    }

    /** A postponed reminder has rung: it leaves its list. */
    @Synchronized
    fun fired(ctx: Context, alarm: Alarm, snoozed: Boolean) {
        if (!snoozed) return
        val prefs = Prefs(ctx)
        prefs.snoozed = Alarm.json(Alarm.list(prefs.snoozed).filter { it.id != alarm.id })
    }

    private fun intent(ctx: Context, id: String, snoozed: Boolean): Intent =
        Intent(ctx, AlarmReceiver::class.java).setAction(ACTION_FIRE)
            .setData(Uri.parse("mamia://alarm/" + (if (snoozed) "s/" else "a/") + Uri.encode(id)))   // one PendingIntent per reminder

    private fun schedule(ctx: Context, alarm: Alarm, snoozed: Boolean) {
        val i = intent(ctx, alarm.id, snoozed).putExtra(EXTRA_ALARM, alarm.json().toString()).putExtra(EXTRA_SNOOZED, snoozed)
        val pi = PendingIntent.getBroadcast(ctx, 0, i, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) {
            try {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, alarm.at, pi)
                return
            } catch (_: SecurityException) { }   // the permission was withdrawn meanwhile
        }
        am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, alarm.at, pi)   // a few minutes late at most
    }

    private fun cancel(ctx: Context, id: String, snoozed: Boolean) {
        val pi = PendingIntent.getBroadcast(ctx, 0, intent(ctx, id, snoozed),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_NO_CREATE) ?: return
        ctx.getSystemService(AlarmManager::class.java)?.cancel(pi)
        pi.cancel()
    }

    fun exactAllowed(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 31 || ctx.getSystemService(AlarmManager::class.java)?.canScheduleExactAlarms() == true
}
