import os
import sys
import subprocess
from .testcase import DBusTestCase

if sys.version_info[0] < 3:
    PIPE_DEVNULL = open(os.devnull, 'wb')

    def Popen(*args, **kwargs):
        if 'pass_fds' in kwargs:
            pass_fds = kwargs['pass_fds']
            del kwargs['pass_fds']
        else:
            pass_fds = []

        orig_preexec_fn = kwargs.get('preexec_fn', None)

        def _setup():
            for fd in range(3, subprocess.MAXFD):
                if fd in pass_fds:
                    continue

                try:
                    os.close(fd)
                except OSError:
                    pass

            if orig_preexec_fn:
                orig_preexec_fn()

        # Don't let subprocess close FDs for us
        kwargs['close_fds'] = False
        kwargs['preexec_fn'] = _setup

        return subprocess.Popen(*args, **kwargs)

else:
    PIPE_DEVNULL = subprocess.DEVNULL
    Popen = subprocess.Popen


class X11SessionTestCase(DBusTestCase):
    #: The display the X server is running on
    X_display = -1
    #: The X server to start
    Xserver = 'Xvfb'
    #: Further parameters for the X server
    Xserver_args = ['-screen', '0', '1280x1024x24', '+extension', 'GLX']
    #: Where to redirect the X stdout and stderr to. Set to None for debugging
    #: purposes if the X server is failing for some reason.
    Xserver_output = PIPE_DEVNULL

    @classmethod
    def setUpClass(klass):
        klass.start_xorg()
        klass.start_system_bus()
        klass.start_session_bus()

    @classmethod
    def start_xorg(klass):
        r, w = os.pipe()

        # Xvfb seems to randomly crash in some workloads if "-noreset" is not given.
        #  https://bugzilla.redhat.com/show_bug.cgi?id=1565847
        klass.xorg = Popen([klass.Xserver, '-displayfd', "%d" % w, '-noreset'] + klass.Xserver_args,
                           pass_fds=(w,),
                           stdout=klass.Xserver_output,
                           stderr=subprocess.STDOUT)
        os.close(w)

        # The X server will write "%d\n", we need to make sure to read the "\n".
        # If the server dies we get zero bytes reads as EOF is reached.
        display = b''
        while True:
            tmp = os.read(r, 1024)
            display += tmp

            # Break out if the read was empty or the line feed was read
            if not tmp or tmp[-1] == b'\n':
                break

        os.close(r)

        try:
            display = int(display.strip())
        except ValueError:
            # This should never happen, the X server didn't return a proper integer.
            # Most likely it died for some odd reason.
            # Note: Set Xserver_output to None to debug Xvfb startup issues.
            klass.stop_xorg()
            raise AssertionError('X server reported back no or an invalid display number (%s)' % (display))

        klass.X_display = display
        # Export information into our environment for tests to use
        os.environ['DISPLAY'] = ":%d" % klass.X_display
        os.environ['WAYLAND'] = ''

        # Server should still be up and running at this point
        assert klass.xorg.poll() is None

        return klass.X_display

    @classmethod
    def stop_xorg(klass):
        if hasattr(klass, 'xorg'):
            klass.X_display = -1
            klass.xorg.terminate()
            klass.xorg.wait()
            del klass.xorg

    @classmethod
    def tearDownClass(klass):
        DBusTestCase.tearDownClass()

        klass.stop_xorg()
