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
import android.util.SparseArray;
import android.view.View;
import android.view.ViewParent;

import com.moez.QKSMS.R;

/**
 * Used by the generated view accessors (see presentation/view-accessors.gradle).
 *
 * This is Java on purpose: without nullability annotations, Kotlin sees the results as platform types, just like
 * the old synthetics. Callers can then use either `view.foo` or `view?.foo`, and a missing view is null instead of
 * an exception thrown by the accessor itself.
 *
 * Like the synthetics, lookups are cached per root view. A cached view is only reused while it's still inside that
 * root, so views that get replaced (an inflated ViewStub, a new content view) are looked up again.
 */
public final class ViewFinder {

    private ViewFinder() {
    }

    public static <T extends View> T find(Activity activity, int id) {
        return find(activity.getWindow().getDecorView(), id);
    }

    @SuppressWarnings("unchecked")
    public static <T extends View> T find(View root, int id) {
        if (root == null) return null;

        SparseArray<View> cache = (SparseArray<View>) root.getTag(R.id.view_finder_cache);
        if (cache == null) {
            cache = new SparseArray<>();
            root.setTag(R.id.view_finder_cache, cache);
        }

        View view = cache.get(id);
        if (view == null || view.getId() != id || !isInside(view, root)) {
            view = root.findViewById(id);
            if (view != null) {
                cache.put(id, view);
            } else {
                cache.remove(id);
            }
        }
        return (T) view;
    }

    private static boolean isInside(View view, View root) {
        if (view == root) return true;
        ViewParent parent = view.getParent();
        while (parent != null) {
            if (parent == root) return true;
            parent = parent.getParent();
        }
        return false;
    }

    public static <T extends View> T find(LayoutContainer container, int id) {
        return find(container.getContainerView(), id);
    }
}
