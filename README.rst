Lenovo ThinkPad Yoga Mode Switcher
==================================

An app indicator for Linux desktop environments running on Lenovo ThinkPad
Yoga laptops that allows manual switching between laptop and tablet modes, plus
orientation changes that take into account the touchscreen.

.. note::

   Due to the different hardware on the Yoga 2, it will likely not work on that
   laptop model.

Requirements
------------

* GObject Introspection bindings for GTK+
* GObject Introspection bindings for AppIndicator_
* PyGObject_
* Any CPython version that supports PyGObject (both 2.x and 3.x)

If you are running GNOME3, you need to install the `appindicator extension`_
for GNOME Shell.

.. _AppIndicator: https://unity.ubuntu.com/projects/appindicators/
.. _PyGObject: https://wiki.gnome.org/Projects/PyGObject
.. _appindicator extension:
   https://extensions.gnome.org/extension/615/appindicator-support/

Installation
------------

User
~~~~

Run ``make install`` - this will put the script into ``~/.local/bin`` (please
add it to your ``PATH`` environment variable if it is not there already) and
add an autostart file for the user's desktop sessions.

System
~~~~~~

Run ``sudo make system-install`` - this will put the script into ``/usr/local/bin``
and add an autostart file for it system-wide.

License
-------

The script is licensed under the GNU General Public License version 3 (or
later), also known as `GPLv3+`_.

.. _GPLv3+: https://www.gnu.org/licenses/gpl-3.0.html
