import os
from enum import Enum
import sys
from typing import Iterable, List
import zipfile

class ModuleType(Enum):
    source = 1
    bytecode = 2
    extension = 3
    package = 4
    namespace_package = 5

class FoundModule:
    def __init__(self, path_in_archive, ext, modtype):
        self.path_in_archive = path_in_archive
        self.ext = ext
        self.modtype = modtype

    def __hash__(self):
        return hash(self.path_in_archive)

    def __eq__(self, other):
        return isinstance(other, FoundModule) \
               and self.path_in_archive == other.path_in_archive

    def __repr__(self):
        return 'FoundModule({!r}, {!r}, {!r})'.format(
            self.path_in_archive, self.ext, self.modtype
        )

    @property
    def path_in_site_packages(self):
        parts = self.path_in_archive.split('/')
        if parts[0].endswith('.dist-info'):
            return None
        elif parts[0].endswith('.data'):
            if len(parts) > 2 and parts[1] in ('platlib', 'purelib'):
                return '/'.join(parts[2:])
            return None
        else:
            return self.path_in_archive

    @property
    def module_name(self):
        path_no_ext = self.path_in_site_packages[:-len(self.ext)]
        return path_no_ext.replace('/', '.')

    @property
    def parent_pkg(self):
        return self.module_name.rpartition('.')[0]

class NamespacePackage:
    modtype = ModuleType.namespace_package
    def __init__(self, module_name):
        self.module_name = module_name

    def __hash__(self):
        return hash(self.module_name)

    def __eq__(self, other):
        return isinstance(other, NamespacePackage) \
               and self.module_name == other.module_name

    def __repr__(self):
        return 'NamespacePackage({!r})'.format(self.module_name)

def get_module_suffixes(wheel_tag):
    py_tag, abi_tag, platform_tag = wheel_tag.split('-')
    d = [
        ('/__init__.py', ModuleType.package),
        # TODO: does __init__.pyc make a package?
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

def find_module_files(namelist, wheel_tag):
    for path in namelist:
        for ext, modtype in get_module_suffixes(wheel_tag):
            if path.endswith(ext):
                res = FoundModule(path, ext, modtype)
                if res.path_in_site_packages is not None:
                    yield res
                break # Don't check more extensions


def find_namespace_packages(modules: List[FoundModule]):
    concrete_pkgs = set()
    for mod in modules:
        if mod.modtype is ModuleType.package:
            concrete_pkgs.add(mod.module_name)

    # TODO: identify non PEP-420 namespace packages
    namespace_pkgs = set()
    for mod in modules:
        pkg = mod.parent_pkg
        if pkg and (pkg not in concrete_pkgs):
            namespace_pkgs.add(pkg)
    for pkgname in sorted(namespace_pkgs):
        yield pkgname

def summarise_modules(modules):
    """Return top-level importable names, and the contents of any namespace packages"""
    nspkg_names = set(find_namespace_packages(modules))
    for mod in sorted(modules, key=lambda m: m.path_in_site_packages):
        parent = mod.parent_pkg
        if (parent == '') or (parent in nspkg_names):
            yield mod

def find_modules_from_whl_path(path):
    name, version, wheel_tag = os.path.basename(path).split('-', 2)
    zf = zipfile.ZipFile(str(path))
    return find_module_files(zf.namelist(), wheel_tag)

def summary_from_whl_path(path):
    modules = list(find_modules_from_whl_path(path))
    return summarise_modules(modules)

if __name__ == '__main__':
    for p in summary_from_whl_path(sys.argv[1]):
        print(p)
