import os
from enum import Enum
import sys
import zipfile

class ModuleType(Enum):
    source = 1
    bytecode = 2
    extension = 3
    package = 4
    namespace_package = 5

def get_module_suffixes(wheel_tag):
    py_tag, abi_tag, platform_tag = wheel_tag.split('-')
    d = [
        ('.py', ModuleType.source),
        ('.pyc', ModuleType.bytecode),
    ]
    if platform_tag.startswith('manylinux'):
        if abi_tag.startswith('cp'):
            # e.g. .cpython-35m-x86_64-linux-gnu.so
            arch = 'x86_64' if platform_tag.endswith('x86_64') else 'i386'
            ext = '.cpython-%s-%s-linux-gnu.so' % (abi_tag[2:], arch)
            d.append((ext, ModuleType.extension))
        elif abi_tag.startswith('abi'):
            # e.g. .abi3.so
            d.append(('.%s.so' % abi_tag, ModuleType.extension))

        d.append(('.so', ModuleType.extension))

    elif platform_tag.startswith('win'):
        d.append(('.pyd', ModuleType.extension))

    # TODO: a load of other cases

    return d

def lib_files(namelist):
    """Find files that would be installed into site-packages"""
    for path in namelist:
        parts = path.split('/')
        if parts[0].endswith('.dist-info'):
            continue
        elif parts[0].endswith('.data'):
            if len(parts) > 2 and parts[1] in ('platlib', 'purelib'):
                yield '/'.join(parts[2:])
        else:
            yield path

def find_module_files(namelist, wheel_tag):
    for path in lib_files(namelist):
        for ext, modtype in get_module_suffixes(wheel_tag):
            if path.endswith(ext):
                yield path, ext, modtype
                break

def parent_pkg(mod: str):
    return mod.rpartition('.')[0]

def identify_modules(namelist):
    concrete_pkgs = set()
    modules = set()
    for path, ext, modtype in namelist:
        parts = path.split('/')
        if len(parts) > 1 and parts[-1] == '__init__.py':  # TODO: does __init__.pyc work?
            pkg = '.'.join(parts[:-1])
            # TODO: identify non PEP-420 namespace packages
            concrete_pkgs.add(pkg)
            yield pkg, ModuleType.package
        else:
            terminal_name = parts[-1][:-len(ext)]
            mod = '.'.join(parts[:-1] + [terminal_name])
            yield mod, modtype
            modules.add(mod)

    namespace_pkgs = set()
    for mod in modules | concrete_pkgs:
        pkg = parent_pkg(mod)
        if pkg and (pkg not in concrete_pkgs):
            namespace_pkgs.add(pkg)
    for nspkg in sorted(namespace_pkgs):
        yield nspkg, ModuleType.namespace_package

def summarise_modules(modules):
    """Return top-level importable names, and the contents of any namespace packages"""
    concrete, namespace_pkgs = set(), set()
    for modname, modtype in modules:
        if modtype is ModuleType.namespace_package:
            namespace_pkgs.add(modname)
        else:
            concrete.add(modname)

    for modname in sorted(concrete):
        parent = parent_pkg(modname)
        if (parent == '') or (parent in namespace_pkgs):
            yield modname

def find_modules_from_whl_path(path):
    name, version, wheel_tag = os.path.basename(path).split('-', 2)
    zf = zipfile.ZipFile(str(path))
    module_files = list(find_module_files(zf.namelist(), wheel_tag))
    return identify_modules(module_files)

if __name__ == '__main__':
    for p in summarise_modules(find_modules_from_whl_path(sys.argv[1])):
        print(p)
