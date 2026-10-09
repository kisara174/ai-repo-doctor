/* SPDX-License-Identifier: MIT; Copyright (c) 2026 kisara174. */
#include <Python.h>

typedef struct TSLanguage TSLanguage;
const TSLanguage *tree_sitter_javascript(void);
const TSLanguage *tree_sitter_tsx(void);

static PyObject *javascript(PyObject *self, PyObject *args) {
    return PyCapsule_New((void *)tree_sitter_javascript(), "tree_sitter.Language", NULL);
}

static PyObject *tsx(PyObject *self, PyObject *args) {
    return PyCapsule_New((void *)tree_sitter_tsx(), "tree_sitter.Language", NULL);
}

static PyMethodDef methods[] = {
    {"language_javascript", javascript, METH_NOARGS, "Patched JavaScript grammar capsule."},
    {"language_tsx", tsx, METH_NOARGS, "Patched TSX grammar capsule."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_binding", NULL, -1, methods
};

PyMODINIT_FUNC PyInit__binding(void) {
    return PyModule_Create(&module);
}
