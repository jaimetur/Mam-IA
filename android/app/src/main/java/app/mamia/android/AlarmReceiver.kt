package app.mamia.android

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

/** A reminder's time has come: its notification. Also "Snooze 10 min", tapped in a notification. */
class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val alarm = Alarm.from(intent.getStringExtra(Alarms.EXTRA_ALARM)) ?: return
        when (intent.action) {
            Alarms.ACTION_FIRE -> {
                Alarms.fired(ctx, alarm, intent.getBooleanExtra(Alarms.EXTRA_SNOOZED, false))
                Notifier.show(ctx, alarm)
            }
            Alarms.ACTION_SNOOZE -> {
                ctx.getSystemService(NotificationManager::class.java)?.cancel(Notifier.id(alarm))
                Alarms.snooze(ctx, alarm)
            }
        }
    }
}

/** The reminders' notifications, on their own channel ("Avisos de Mam-IA"). */
object Notifier {
    const val CHANNEL = "avisos"
    const val EXTRA_NOTIFICATION = "notification"

    fun id(alarm: Alarm): Int = alarm.id.hashCode()

    fun ensureChannel(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        if (nm.getNotificationChannel(CHANNEL) != null) return
        nm.createNotificationChannel(NotificationChannel(CHANNEL, ctx.getString(R.string.channel_name),
            NotificationManager.IMPORTANCE_HIGH).apply { description = ctx.getString(R.string.channel_description) })
    }

    /** Notifications can be shown: the permission (Android 13+) and the app's notifications switched on. */
    fun allowed(ctx: Context): Boolean {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return false
        val perm = Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        return perm && nm.areNotificationsEnabled()
    }

    fun show(ctx: Context, alarm: Alarm) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        ensureChannel(ctx)
        val nid = id(alarm)
        val server = Prefs(ctx).server
        // tap: the reminder's page in the app; "Done": the web app marks it done (?hecho=<id>)
        val open = page(ctx, if (server.isEmpty()) null else server + alarm.path, nid, 0)
        val done = page(ctx, if (server.isEmpty()) null else "$server/app?hecho=" + Uri.encode(alarm.id), nid, 1)
        val snooze = PendingIntent.getBroadcast(ctx, 0,
            Intent(ctx, AlarmReceiver::class.java).setAction(Alarms.ACTION_SNOOZE)
                .setData(Uri.parse("mamia://snooze/" + Uri.encode(alarm.id)))
                .putExtra(Alarms.EXTRA_ALARM, alarm.json().toString()),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setColor(ContextCompat.getColor(ctx, R.color.accent))
            .setContentTitle(alarm.title)
            .setContentText(alarm.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(alarm.body))
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setWhen(alarm.at).setShowWhen(true)
            .setAutoCancel(true)
            .setContentIntent(open)
            .addAction(0, ctx.getString(R.string.action_done), done)
            .addAction(0, ctx.getString(R.string.action_snooze), snooze)
            .build()
        nm.notify(nid, n)
    }

    private fun page(ctx: Context, url: String?, nid: Int, kind: Int): PendingIntent {
        val i = Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            .putExtra(EXTRA_NOTIFICATION, nid)
        if (url != null) i.setAction(Intent.ACTION_VIEW).setData(Uri.parse(url))
        else i.setAction("app.mamia.android.OPEN.$kind.$nid")   // still one PendingIntent per notification and button
        return PendingIntent.getActivity(ctx, nid * 2 + kind, i, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }
}
