from . import create
from . import paint
from . import scale

_modules = (create, paint, scale)


def register():
    for module in _modules:
        module.register()


def unregister():
    for module in reversed(_modules):
        module.unregister()
