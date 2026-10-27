use std::ffi::{CStr, c_char, c_int};

use vapoursynth4_rs::{
    core::CoreRef,
    ffi::{VSCoreCreationFlags, VSMap, VSNode, vs_make_version},
};

const API_4_2: c_int = vs_make_version(4, 2);
const API_4_3: c_int = vs_make_version(4, 3);
const API_4_3_NEW_FNS_COUNT: usize = 5;

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct GraphApiFns {
    pub(crate) function_name:
        unsafe extern "system-unwind" fn(node: *mut VSNode, level: c_int) -> *const c_char,
    pub(crate) plugin_id:
        unsafe extern "system-unwind" fn(node: *mut VSNode, level: c_int) -> *const c_char,
    pub(crate) plugin_ns:
        unsafe extern "system-unwind" fn(node: *mut VSNode, level: c_int) -> *const c_char,
    pub(crate) function_arguments:
        unsafe extern "system-unwind" fn(node: *mut VSNode, level: c_int) -> *const VSMap,
}

impl GraphApiFns {
    /// Resolves the experimental graph inspection function pointers from the core's API table.
    pub(crate) fn resolve(core: CoreRef<'_>) -> Result<Self, &'static CStr> {
        let info = core.get_info2();
        let is_inspection_enabled =
            (info.creation_flags & (VSCoreCreationFlags::EnableGraphInspection as c_int)) != 0;
        if !is_inspection_enabled {
            return Err(c"Graph: EnableGraphInspection is not enabled on this core");
        }

        let api = core.api();
        let runtime_api = unsafe { (api.getAPIVersion)() };
        let ptr_offset = match runtime_api {
            API_4_2 => 0,
            API_4_3 => API_4_3_NEW_FNS_COUNT,
            _ => {
                return Err(
                    c"Graph: Unsupported VapourSynth API version for graph inspection (requires API 4.2 or 4.3)",
                );
            }
        };

        let base_ptr = (&raw const api.getNodeCreationFunctionName).cast::<*const ()>();
        // SAFETY: When EnableGraphInspection is enabled, the function table extension is guaranteed
        // to be present at the layout offset matching the runtime API version.
        let fns = unsafe { *base_ptr.add(ptr_offset).cast::<Self>() };
        Ok(fns)
    }
}
