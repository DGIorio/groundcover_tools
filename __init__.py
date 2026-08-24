# DGI Groundcover Tools - a Blender extension for painting and editing
# the per-object / instanced groundcover.
#
# Registration only; each submodule owns its own register()/unregister().

from . import props
from . import operators
from . import ui

_modules = (props, operators, ui)


def register():
    for module in _modules:
        module.register()


def unregister():
    for module in reversed(_modules):
        module.unregister()
