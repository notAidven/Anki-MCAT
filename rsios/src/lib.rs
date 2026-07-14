// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! `rsios` is a thin C-ABI wrapper around Anki's Rust `Backend`, so the shared
//! engine (`rslib`) can be driven from Swift on iOS.
//!
//! It mirrors what `pylib/rsbridge` does for Python (via PyO3), but exposes a
//! plain C interface instead: callers pass a protobuf-encoded request as
//! `(service_index, method_index, input_bytes)` and receive the
//! protobuf-encoded response bytes back. The exact same backend command
//! dispatch path (`Backend::run_service_method`) is reused, so there is no
//! second implementation of any engine logic.
//!
//! Memory ownership rules (important for the Swift side):
//! * Any `*mut u8` buffer returned through an out-pointer is owned by the
//!   caller and MUST be released with [`rsios_free_buffer`].
//! * The opaque backend handle returned by [`rsios_open_backend`] MUST be
//!   released with [`rsios_close_backend`].

use std::slice;

use anki::backend::init_backend;
use anki::backend::Backend;

/// Opaque handle handed back to Swift. The real `Backend` lives behind it.
pub struct RsiosBackend {
    inner: Backend,
}

/// Status codes returned by the FFI functions.
pub const RSIOS_OK: i32 = 0;
/// The backend ran but returned an error; the out-buffer holds an encoded
/// `anki.backend.BackendError` protobuf message.
pub const RSIOS_BACKEND_ERROR: i32 = 1;
/// A null pointer was passed where one was required.
pub const RSIOS_NULL_POINTER: i32 = -1;

/// Take ownership of a `Vec<u8>` and hand a thin pointer + length back to C.
///
/// We go through a boxed slice so capacity == length, which makes the matching
/// free in [`rsios_free_buffer`] sound.
fn vec_into_raw(bytes: Vec<u8>, out_ptr: *mut *mut u8, out_len: *mut usize) {
    let boxed = bytes.into_boxed_slice();
    let len = boxed.len();
    let ptr = Box::into_raw(boxed) as *mut u8;
    unsafe {
        *out_ptr = ptr;
        *out_len = len;
    }
}

/// Open a backend from a protobuf-encoded `anki.backend.BackendInit` message.
///
/// `init_ptr`/`init_len` may describe an empty buffer (or `init_ptr` may be
/// null with `init_len == 0`), in which case a default init is used.
///
/// On success returns a non-null handle and leaves the out-error buffer empty.
/// On failure returns null and, if `out_err_ptr`/`out_err_len` are non-null,
/// writes a UTF-8 error message (NOT null-terminated; use the length) that the
/// caller must release with [`rsios_free_buffer`].
///
/// # Safety
/// `init_ptr` must be valid for `init_len` bytes (or null when `init_len ==
/// 0`).
#[no_mangle]
pub unsafe extern "C" fn rsios_open_backend(
    init_ptr: *const u8,
    init_len: usize,
    out_err_ptr: *mut *mut u8,
    out_err_len: *mut usize,
) -> *mut RsiosBackend {
    if !out_err_ptr.is_null() {
        *out_err_ptr = std::ptr::null_mut();
    }
    if !out_err_len.is_null() {
        *out_err_len = 0;
    }

    let init: &[u8] = if init_ptr.is_null() || init_len == 0 {
        &[]
    } else {
        slice::from_raw_parts(init_ptr, init_len)
    };

    match init_backend(init) {
        Ok(inner) => Box::into_raw(Box::new(RsiosBackend { inner })),
        Err(e) => {
            if !out_err_ptr.is_null() && !out_err_len.is_null() {
                vec_into_raw(e.into_bytes(), out_err_ptr, out_err_len);
            }
            std::ptr::null_mut()
        }
    }
}

/// Run a single backend command, identical to the dispatch used by the Python
/// bridge: `Backend::run_service_method(service, method, input)`.
///
/// Writes the response bytes to `out_ptr`/`out_len`. The return value
/// distinguishes a successful response ([`RSIOS_OK`]) from a backend error
/// ([`RSIOS_BACKEND_ERROR`], where the buffer holds an encoded `BackendError`).
/// In both of those cases the buffer must be freed with [`rsios_free_buffer`].
///
/// # Safety
/// `backend` must be a handle previously returned by [`rsios_open_backend`] and
/// not yet closed. `input_ptr` must be valid for `input_len` bytes (or null
/// when `input_len == 0`). `out_ptr`/`out_len` must be valid for writes.
#[no_mangle]
pub unsafe extern "C" fn rsios_command(
    backend: *mut RsiosBackend,
    service: u32,
    method: u32,
    input_ptr: *const u8,
    input_len: usize,
    out_ptr: *mut *mut u8,
    out_len: *mut usize,
) -> i32 {
    if backend.is_null() || out_ptr.is_null() || out_len.is_null() {
        return RSIOS_NULL_POINTER;
    }
    *out_ptr = std::ptr::null_mut();
    *out_len = 0;

    let backend = &*backend;
    let input: &[u8] = if input_ptr.is_null() || input_len == 0 {
        &[]
    } else {
        slice::from_raw_parts(input_ptr, input_len)
    };

    match backend.inner.run_service_method(service, method, input) {
        Ok(out_bytes) => {
            vec_into_raw(out_bytes, out_ptr, out_len);
            RSIOS_OK
        }
        Err(err_bytes) => {
            vec_into_raw(err_bytes, out_ptr, out_len);
            RSIOS_BACKEND_ERROR
        }
    }
}

/// Free a buffer previously returned by [`rsios_open_backend`] or
/// [`rsios_command`]. Passing a null pointer is a no-op.
///
/// # Safety
/// `ptr`/`len` must be a buffer produced by this library and not freed before.
#[no_mangle]
pub unsafe extern "C" fn rsios_free_buffer(ptr: *mut u8, len: usize) {
    if ptr.is_null() {
        return;
    }
    let slice = slice::from_raw_parts_mut(ptr, len);
    drop(Box::from_raw(slice as *mut [u8]));
}

/// Close a backend handle and release its resources (including any open
/// collection). Passing a null pointer is a no-op.
///
/// # Safety
/// `backend` must be a handle previously returned by [`rsios_open_backend`] and
/// not yet closed.
#[no_mangle]
pub unsafe extern "C" fn rsios_close_backend(backend: *mut RsiosBackend) {
    if backend.is_null() {
        return;
    }
    drop(Box::from_raw(backend));
}

/// Returns the Anki build hash as a null-terminated C string with static
/// lifetime (do NOT free). Useful as a "is the engine linked?" smoke test.
#[no_mangle]
pub extern "C" fn rsios_buildhash() -> *const std::os::raw::c_char {
    // anki::version::buildhash() returns a &'static str without a trailing NUL.
    // We build a NUL-terminated static once.
    use std::sync::OnceLock;
    static HASH: OnceLock<std::ffi::CString> = OnceLock::new();
    HASH.get_or_init(|| std::ffi::CString::new(anki::version::buildhash()).unwrap_or_default())
        .as_ptr()
}
