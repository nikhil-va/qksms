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
package com.moez.QKSMS.common

import android.app.Activity
import android.content.Context
import android.widget.LinearLayout
import android.widget.TextView
import androidx.annotation.StringRes
import androidx.core.widget.TextViewCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.bottomsheet.BottomSheetDragHandleView
import com.moez.QKSMS.R
import com.moez.QKSMS.common.util.extensions.dpToPx
import com.moez.QKSMS.common.util.extensions.resolveThemeColor
import com.moez.QKSMS.common.util.extensions.setPadding
import com.moez.QKSMS.injection.appComponent
import javax.inject.Inject

/**
 * Shows a list of options that use our UI, as a bottom sheet (within thumb reach, like Google's apps)
 */
class QkDialog @Inject constructor(private val context: Context, val adapter: MenuItemAdapter) {

    var title: String? = null

    init {
        appComponent.inject(this)
    }

    fun show(activity: Activity) {
        val recyclerView = RecyclerView(activity)
        recyclerView.layoutManager = LinearLayoutManager(context)
        recyclerView.adapter = adapter
        recyclerView.setPadding(top = 8.dpToPx(context), bottom = 8.dpToPx(context))

        val content = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(bottom = activity.resources.getDimensionPixelSize(R.dimen.thumb_reach_padding))
            addView(BottomSheetDragHandleView(activity))
            title?.let { title ->
                addView(TextView(activity).apply {
                    TextViewCompat.setTextAppearance(this, com.google.android.material.R.style.TextAppearance_Material3_TitleLarge)
                    setTextColor(activity.resolveThemeColor(android.R.attr.textColorPrimary))
                    setPadding(left = 24.dpToPx(context), right = 24.dpToPx(context), bottom = 8.dpToPx(context))
                    text = title
                })
            }
            addView(recyclerView)
        }

        val dialog = BottomSheetDialog(activity)
        dialog.setContentView(content)
        dialog.behavior.state = BottomSheetBehavior.STATE_EXPANDED
        dialog.behavior.skipCollapsed = true

        val clicks = adapter.menuItemClicks
                .subscribe { dialog.dismiss() }

        dialog.setOnDismissListener {
            clicks.dispose()
        }

        dialog.show()
    }

    fun setTitle(@StringRes title: Int) {
        this.title = context.getString(title)
    }

}