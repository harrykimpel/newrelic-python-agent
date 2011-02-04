/* ------------------------------------------------------------------------- */

/* (C) Copyright 2010-2011 New Relic Inc. All rights reserved. */

/* ------------------------------------------------------------------------- */

#include "py_web_transaction.h"

#include "globals.h"

/* ------------------------------------------------------------------------- */

static int NRWebTransaction_init(NRTransactionObject *self, PyObject *args,
                                 PyObject *kwds)
{
    NRApplicationObject *application = NULL;
    PyObject *environ = NULL;

    PyObject *newargs = NULL;
    PyObject *object = NULL;

    const char *tmppath = NULL;

    const char *realpath = "<unknown>";
    const char *path = "<unknown>";
    int path_type = NR_PATH_TYPE_UNKNOWN;
    int64_t queue_start = 0;

    static char *kwlist[] = { "application", "environ", NULL };

    /*
     * For the case that no argument was provided then the new
     * method would have returned a reference to an existing
     * in progress transaction instance which has already been
     * initialised. We check for this case and skip doing any
     * initialisation a second time. We also return here if the
     * init method has been called twice when it should not
     * have been.
     */

    if (self->application)
        return 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O!O!:WebTransaction",
                                     kwlist, &NRApplication_Type,
                                     &application, &PyDict_Type, &environ)) {
        return -1;
    }

    newargs = PySequence_GetSlice(args, 0, 1);

    if (NRTransaction_Type.tp_init((PyObject *)self, newargs, kwds) < 0) {
        Py_DECREF(newargs);
        return -1;
    }

    Py_DECREF(newargs);

    /*
     * XXX Don't need to bother to extract details if not
     * real transaction.
     */

    /*
     * Extract from the WSGI environ dictionary details of the
     * URL path. This will be set as default path for the web
     * transaction. This can be overridden by framework to be
     * more specific to avoid metrics explosion problem resulting
     * from too many distinct URLs for same resource due to use
     * of REST style URL concepts or otherwise.
     *
     * TODO Note that we only pay attention to REQUEST_URI at
     * this time. In the PHP agent it is possible to base the
     * path on the filename of the resource, but this may not
     * necessarily be appropriate for WSGI. Instead may be
     * necessary to look at reconstructing equivalent of the
     * REQUEST_URI from SCRIPT_NAME and PATH_INFO instead where
     * REQUEST_URI is not available. Ultimately though expect
     * that path will be set to be something more specific by
     * higher level wrappers for a specific framework.
     */

    object = PyDict_GetItemString(environ, "REQUEST_URI");

    if (object && PyString_Check(object))
        tmppath = PyString_AsString(object);

    if (tmppath) {
        path = tmppath;
        realpath = tmppath;
        path_type = NR_PATH_TYPE_URI;
    }

    /*
     * See if the WSGI environ dictionary includes the special
     * 'X-NewRelic-Queue-Start' HTTP header. This header is an
     * optional header that can be set within the underlying web
     * server or WSGI server to indicate when the current
     * request was first received and ready to be processed. The
     * difference between this time and when application starts
     * processing the request is the queue time and represents
     * how long spent in any explicit request queuing system, or
     * how long waiting in connecting state against listener
     * sockets where request needs to be proxied between any
     * processes within the application server.
     */

    object = PyDict_GetItemString(environ, "HTTP_X_NEWRELIC_QUEUE_START");

    if (object && PyString_Check(object)) {
        const char *s = PyString_AsString(object);
        if (s[0] == 't' && s[1] == '=' )
            queue_start = (int64_t)strtoll(s+2, 0, 0);
    }

    /*
     * Setup the background task specific attributes of the
     * transaction.
     */

    if (self->transaction) {
        self->transaction->path_type = path_type;
        self->transaction->path = nrstrdup(path);
        self->transaction->realpath = nrstrdup(realpath);

        self->transaction->http_x_request_start = queue_start;

        PyDict_Update(self->request_parameters, environ);
    }

    return 0;
}


/* ------------------------------------------------------------------------- */

#ifndef PyVarObject_HEAD_INIT
#define PyVarObject_HEAD_INIT(type, size) PyObject_HEAD_INIT(type) size,
#endif

PyTypeObject NRWebTransaction_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "_newrelic.WebTransaction", /*tp_name*/
    sizeof(NRTransactionObject), /*tp_basicsize*/
    0,                      /*tp_itemsize*/
    /* methods */
    0,                      /*tp_dealloc*/
    0,                      /*tp_print*/
    0,                      /*tp_getattr*/
    0,                      /*tp_setattr*/
    0,                      /*tp_compare*/
    0,                      /*tp_repr*/
    0,                      /*tp_as_number*/
    0,                      /*tp_as_sequence*/
    0,                      /*tp_as_mapping*/
    0,                      /*tp_hash*/
    0,                      /*tp_call*/
    0,                      /*tp_str*/
    0,                      /*tp_getattro*/
    0,                      /*tp_setattro*/
    0,                      /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,     /*tp_flags*/
    0,                      /*tp_doc*/
    0,                      /*tp_traverse*/
    0,                      /*tp_clear*/
    0,                      /*tp_richcompare*/
    0,                      /*tp_weaklistoffset*/
    0,                      /*tp_iter*/
    0,                      /*tp_iternext*/
    0,                      /*tp_methods*/
    0,                      /*tp_members*/
    0,                      /*tp_getset*/
    &NRTransaction_Type,    /*tp_base*/
    0,                      /*tp_dict*/
    0,                      /*tp_descr_get*/
    0,                      /*tp_descr_set*/
    0,                      /*tp_dictoffset*/
    (initproc)NRWebTransaction_init, /*tp_init*/
    0,                      /*tp_alloc*/
    0,                      /*tp_new*/
    0,                      /*tp_free*/
    0,                      /*tp_is_gc*/
};

/* ------------------------------------------------------------------------- */

/*
 * vim: et cino=>2,e0,n0,f0,{2,}0,^0,\:2,=2,p2,t2,c1,+2,(2,u2,)20,*30,g2,h2 ts=8
 */
