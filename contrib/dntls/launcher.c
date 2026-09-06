/*
 * launcher embeds CPython in-process so that the wallet's main executable is
 * this code-signed image, which carries the DNTLS program attestation marker.
 *
 * The Local Trust Resolver identifies a calling program by its main
 * executable: the image must be validly signed and contain exactly one
 * attestation marker that the program's DNTLS name signed. A Python
 * interpreter cannot be attested that way, but a small signed launcher that
 * loads libpython can. Placed in a virtual environment's bin directory, it
 * behaves as that environment's python: CPython finds pyvenv.cfg next to it.
 *
 * DNTLS_MARKER is supplied at compile time by build.sh after the provisional
 * (marker-less) build has been signed and measured.
 */
#include <Python.h>
#include <stdio.h>
#include <string.h>

#ifndef DNTLS_MARKER
#define DNTLS_MARKER "unset"
#endif

static const char dntls_attestation[] = DNTLS_MARKER;

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--dntls-marker") == 0) {
        fputs(dntls_attestation, stdout);
        fputc('\n', stdout);
        return 0;
    }
    return Py_BytesMain(argc, argv);
}
