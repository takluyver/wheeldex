Index the Python modules inside a wheel

Wheels are the modern distribution format for Python modules and packages.
This tool can read a wheel and list the modules found inside it.
Hopefully it will help to produce an index so you can find packages by the
import name (which can be different from the name on PyPI).

Example use with the command line::

    $ python3 -m wheeldex pyzmq-16.0.2-cp27-cp27mu-manylinux1_x86_
    ................... 64.whl
    1 top-level modules:
      zmq

    $ python3 -m wheeldex backports.shutil_get_terminal_size-1.0.0
    ................... -py2.py3-none-any.whl
    1 top-level modules:
      shutil_backports
    backports namespace package (1):
      backports.shutil_get_terminal_size
