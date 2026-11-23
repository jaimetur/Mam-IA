package app.mamia.android

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Android forgets the scheduled alarms when the phone restarts or the app is updated: they are set again. Also when
 *  the exact-alarm permission changes (from then on they ring at their exact time). */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action in ACTIONS) Alarms.rescheduleAll(ctx)
    }

    private companion object {
        val ACTIONS = setOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED,
            "android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED")
    }
}
