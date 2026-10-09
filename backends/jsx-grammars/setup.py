"""Build only the companion extension; the main CLI remains a pure Python wheel."""
from pathlib import Path
from setuptools import Extension, setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        self.copy_file('provenance.json', str(Path(self.build_lib) / 'ai_repo_doctor_grammars/provenance.json'))


setup(
    packages=['ai_repo_doctor_grammars'],
    package_dir={'': 'src'},
    ext_modules=[Extension(
        'ai_repo_doctor_grammars._binding',
        sources=['src/ai_repo_doctor_grammars/binding.c',
                 'vendor/javascript/src/parser.c', 'vendor/javascript/src/scanner.c',
                 'vendor/typescript/tsx/src/parser.c', 'vendor/typescript/tsx/src/scanner.c'],
        include_dirs=['vendor/javascript/src', 'vendor/typescript/tsx/src'],
        define_macros=[('Py_LIMITED_API', '0x030B0000'), ('PY_SSIZE_T_CLEAN', None),
                       ('TREE_SITTER_HIDE_SYMBOLS', None)],
        extra_compile_args=['-std=c11', '-fvisibility=hidden'],
        py_limited_api=True,
    )],
    cmdclass={'build_py': BuildPy},
    options={'bdist_wheel': {'py_limited_api': 'cp311'}},
)
