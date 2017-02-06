import ast
from astcheck import name_or_attr
import astsearch
import os
from os.path import basename, splitext
from enum import Enum
import sys
from typing import Iterable, List
import zipfile

from collections import defaultdict


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
        if py_tag.startswith('cp'):
            d.append(('.%s-%s.pyd' % (py_tag, platform_tag), ModuleType.extension))
        d.append(('.pyd', ModuleType.extension))

    # TODO: a load of other cases

    return d

def check_namespace_pkg(init_code):
    init_ast = ast.parse(init_code)
    pat = ast.Assign(targets=[ast.Name(id='__path__')],
                     values=ast.Call(func=name_or_attr('extend_path')))
    matches = astsearch.ASTPatternFinder(pat).scan_ast(init_ast)
    return bool(list(matches))

def find_module_files(zf: zipfile.ZipFile, wheel_tag):
    for path in zf.namelist():
        if path.endswith('/__init__.py'):
            modtype = ModuleType.package
            if check_namespace_pkg(zf.read(path)):
                modtype = ModuleType.namespace_package
            yield FoundModule(path, '/__init__.py', modtype)
            continue

        for ext, modtype in get_module_suffixes(wheel_tag):
            if path.endswith(ext):
                res = FoundModule(path, ext, modtype)
                if res.path_in_site_packages is not None:
                    yield res
                break # Don't check more extensions


def find_namespace_packages(modules: List[FoundModule]):
    concrete_pkgs = set()
    namespace_pkgs = set()
    for mod in modules:
        if mod.modtype is ModuleType.package:
            concrete_pkgs.add(mod.module_name)
        if mod.modtype is ModuleType.namespace_package:
            namespace_pkgs.add(mod.module_name)

    # Identify PEP 420 namespace packages, which are directories containing
    # modules *without* an __init__.py
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
    name, version, wheel_tag = splitext(basename(path))[0].split('-', 2)
    zf = zipfile.ZipFile(str(path))
    return find_module_files(zf, wheel_tag)

def summary_from_whl_path(path):
    modules = list(find_modules_from_whl_path(path))
    return summarise_modules(modules)

def print_summary_from_whl_path(path):
    modules = list(find_modules_from_whl_path(path))

    toplevel_modules = sorted([m.module_name for m in modules
                           if not m.parent_pkg \
                           and m.modtype is not ModuleType.namespace_package])
    print(len(toplevel_modules), 'top-level modules:')
    for modname in toplevel_modules:
        print(' ', modname)

    nspkg_contents = {name: [] for name in find_namespace_packages(modules)}
    for mod in modules:
        parent = mod.parent_pkg
        if parent in nspkg_contents:
            nspkg_contents[parent].append(mod)

    for nspkg, contents in sorted(nspkg_contents.items()):
        print(nspkg, 'namespace package ({}):'.format(len(contents)))
        for modname in sorted([m.module_name for m in contents]):
            print(' ', modname)


if __name__ == '__main__':
    print_summary_from_whl_path(sys.argv[1])
