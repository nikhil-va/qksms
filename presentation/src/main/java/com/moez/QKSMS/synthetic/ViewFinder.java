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
package com.moez.QKSMS.synthetic;

import android.app.Activity;
import android.view.View;

/**
 * Used by the generated view accessors (see presentation/view-accessors.gradle).
 *
 * This is Java on purpose: without nullability annotations, Kotlin sees the results as platform types, just like
 * the old synthetics. Callers can then use either `view.foo` or `view?.foo`, and a missing view is null instead of
 * an exception thrown by the accessor itself.
 */
public final class ViewFinder {

    private ViewFinder() {
    }

    public static <T extends View> T find(Activity activity, int id) {
        return activity.findViewById(id);
    }

    public static <T extends View> T find(View root, int id) {
        return root == null ? null : root.<T>findViewById(id);
    }

    public static <T extends View> T find(LayoutContainer container, int id) {
        return find(container.getContainerView(), id);
    }
}
