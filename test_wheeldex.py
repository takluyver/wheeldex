from wheeldex import (ModuleType, find_module_files, find_namespace_packages,
    check_namespace_pkg,
)

class FakeZipFile:
    def __init__(self, contents: dict):
        self.contents = contents

    def namelist(self):
        return list(self.contents)

    def read(self, path):
        return self.contents[path]

# The standard declaration of a non PEP-420 namespace package
NS_PKG_DECL = b'''\
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
'''

sample1 = FakeZipFile({
    'top_level.cpython-36m-i386-linux-gnu.so': b'',
    'top_level2.py': b'',
    'apkg/__init__.py': b'',
    'namespace1/foo.py': b'',
    'namespace2/__init__.py': NS_PKG_DECL,
    'namespace2/bar.py': '',
})

def test_find_modules():
    res = set(find_module_files(sample1, 'cp36-cp36m-manylinux1_i686'))
    by_name = {m.module_name: m for m in res}
    assert set(by_name) == {'top_level', 'top_level2', 'namespace1.foo',
                            'namespace2', 'namespace2.bar', 'apkg'}
    assert by_name['top_level'].modtype == ModuleType.extension
    assert by_name['top_level2'].modtype == ModuleType.source
    assert by_name['apkg'].modtype == ModuleType.package
    assert by_name['namespace1.foo'].modtype == ModuleType.source
    assert by_name['namespace2'].modtype == ModuleType.namespace_package
    assert by_name['namespace2.bar'].modtype == ModuleType.source

def test_find_namespace_packages():
    mods = list(find_module_files(sample1, 'cp36-cp36m-manylinux1_i686'))
    ns = set(find_namespace_packages(mods))
    assert ns == {'namespace1', 'namespace2'}

def test_check_namespace_pkg():
    assert check_namespace_pkg(NS_PKG_DECL)
    assert not check_namespace_pkg(b'')
    # We look for '__path__ == extend_path(...)'
    assert not check_namespace_pkg(b'foo = extend_path()')
    assert not check_namespace_pkg(b'raise = 2')
