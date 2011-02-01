/* ------------------------------------------------------------------------- */

/* (C) Copyright 2010-2011 New Relic Inc. All rights reserved. */

/* ------------------------------------------------------------------------- */

#include "py_traceback.h"

/* ------------------------------------------------------------------------- */

PyObject *nrpy__format_exception(PyObject *type, PyObject *value,
                                 PyObject *traceback)
{
    PyObject *module = NULL;
    PyObject *stack_trace = NULL;

    /*
     * If we don't believe we have been given value valid
     * exception info return None.
     */

    if (type == Py_None && value == Py_None && traceback == Py_None) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    /*
     * Generate a formatted stack trace with the details of
     * exception. We don't check the types of the arguments if
     * all are not None. If any are wrong that should be picked
     * up by the code below and they will flag the error.
     */

    module = PyImport_ImportModule("traceback");

    if (module) {
        PyObject *dict = NULL;
        PyObject *object = NULL;

        dict = PyModule_GetDict(module);
        object = PyDict_GetItemString(dict, "format_exception");

        if (object) {
            PyObject *result = NULL;

            Py_INCREF(object);

            result = PyObject_CallFunctionObjArgs(object, type,
                                           value, traceback, NULL);

            Py_DECREF(object);

            if (result) {
                PyObject *sep = NULL;

                sep = PyString_FromString("");
                stack_trace = _PyString_Join(sep, result);

                Py_DECREF(sep);
                Py_DECREF(result);
            }
        }

        Py_DECREF(module);
    }

    return stack_trace;
}

/* ------------------------------------------------------------------------- */
