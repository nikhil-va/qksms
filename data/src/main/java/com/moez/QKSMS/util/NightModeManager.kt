/*
 * Copyright (C) 2017 Moez Bhatti <moez.bhatti@gmail.com>
 *
 * This file is part of QKSMS.
 *
 * QKSMS is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * QKSMS is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with QKSMS.  If not, see <http://www.gnu.org/licenses/>.
 */
package com.moez.QKSMS.util

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.appcompat.app.AppCompatDelegate
import com.moez.QKSMS.manager.WidgetManager
import com.moez.QKSMS.receiver.NightModeReceiver
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NightModeManager @Inject constructor(
    private val context: Context,
    private val prefs: Preferences,
    private val widgetManager: WidgetManager
) {

    /**
     * The app follows the system's light/dark setting. Also cancels the alarms of the old scheduled night mode,
     * in case they were set before it was removed.
     */
    fun updateCurrentTheme() {
        AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM)

        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        listOf(0, 1)
                .map { requestCode -> Intent(context, NightModeReceiver::class.java) to requestCode }
                .mapNotNull { (intent, requestCode) ->
                    PendingIntent.getBroadcast(context, requestCode, intent, PendingIntent.FLAG_NO_CREATE)
                }
                .forEach(alarmManager::cancel)
    }

}