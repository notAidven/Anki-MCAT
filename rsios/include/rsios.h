// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// C interface for `rsios`, the thin C-ABI wrapper around Anki's Rust backend
// (rslib). Callers pass a protobuf-encoded request as
// (service_index, method_index, input_bytes) and receive protobuf-encoded
// response bytes back, reusing Backend::run_service_method.

#ifndef RSIOS_H
#define RSIOS_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Opaque handle to an Anki backend (and its open collection, if any).
typedef struct RsiosBackend RsiosBackend;

// Status codes returned by rsios_command.
#define RSIOS_OK 0            // success; out-buffer holds the response bytes
#define RSIOS_BACKEND_ERROR 1 // backend error; out-buffer holds an encoded
                              // anki.backend.BackendError protobuf
#define RSIOS_NULL_POINTER (-1) // a required pointer argument was null

// Open a backend from a protobuf-encoded anki.backend.BackendInit message.
// init_ptr may be NULL when init_len == 0 (a default init is used).
// On success returns a non-null handle. On failure returns NULL and, when
// out_err_ptr/out_err_len are non-null, writes a UTF-8 error message (not
// null-terminated; use the length) that must be released with
// rsios_free_buffer.
RsiosBackend *rsios_open_backend(const uint8_t *init_ptr,
                                 size_t init_len,
                                 uint8_t **out_err_ptr,
                                 size_t *out_err_len);

// Run one backend command (same dispatch as the Python bridge).
// Writes response bytes to *out_ptr / *out_len. Returns RSIOS_OK or
// RSIOS_BACKEND_ERROR (both allocate a buffer the caller must free with
// rsios_free_buffer), or RSIOS_NULL_POINTER.
int32_t rsios_command(RsiosBackend *backend,
                      uint32_t service,
                      uint32_t method,
                      const uint8_t *input_ptr,
                      size_t input_len,
                      uint8_t **out_ptr,
                      size_t *out_len);

// Free a buffer previously returned by rsios_open_backend or rsios_command.
// Passing NULL is a no-op.
void rsios_free_buffer(uint8_t *ptr, size_t len);

// Close a backend handle and release its resources. Passing NULL is a no-op.
void rsios_close_backend(RsiosBackend *backend);

// Returns the Anki build hash as a static, null-terminated C string (do not
// free). Useful as a smoke test that the engine is linked.
const char *rsios_buildhash(void);

#ifdef __cplusplus
}
#endif

#endif // RSIOS_H
