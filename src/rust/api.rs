use std::ffi::{CStr, c_char, c_int};

use vapoursynth4_rs::{
    core::CoreRef,
    ffi::{
        VSAudioFormat,
        VSColorFamily,
        VSCoreCreationFlags,
        VSFrame,
        VSMap,
        VSNode,
        VSVideoFormat,
        vs_make_version,
    },
};

#[rustfmt::skip]
type NodeLevelFn<R = *const c_char> = unsafe extern "system-unwind" fn(node: *mut VSNode, level: c_int) -> R;
type NodeFn<R> = unsafe extern "system-unwind" fn(node: *mut VSNode) -> R;
type FrameFn<R> = unsafe extern "system-unwind" fn(frame: *const VSFrame) -> R;

const API_4_2: c_int = vs_make_version(4, 2);
const API_4_3: c_int = vs_make_version(4, 3);
const API_4_3_NEW_FNS_COUNT: usize = 5;

#[repr(C)]
#[derive(Clone, Copy)]
struct RawGraphFns {
    function_name: NodeLevelFn,
    plugin_id: NodeLevelFn,
    plugin_ns: NodeLevelFn,
    function_arguments: NodeLevelFn<*const VSMap>,
}

#[derive(Clone, Copy)]
pub(crate) struct GraphApiFns {
    get_node_residency: Option<NodeFn<c_int>>,
    get_frame_residency: Option<FrameFn<c_int>>,
    function_name: NodeLevelFn,
    plugin_id: NodeLevelFn,
    plugin_ns: NodeLevelFn,
    function_arguments: NodeLevelFn<*const VSMap>,
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

        // Anchor right after getCoreInfo2, the last common function between API 4.2 and 4.3 in vapoursynth4-sys
        let api_ext_base = unsafe { (&raw const api.getCoreInfo2).cast::<*const ()>().add(1) };

        let (graph_fns_offset, get_node_residency, get_frame_residency) = match runtime_api {
            API_4_2 => (0, None, None),
            API_4_3 => {
                // Offsets after getCoreInfo2 in VapourSynth4.h:
                // +0: createVideoFilterEx
                // +1: createVideoFilterEx2
                // +2: getVulkanAPI
                // +3: getNodeResidency
                // +4: getFrameResidency
                // +5: getNodeCreationFunctionName
                let node_res = unsafe {
                    *api_ext_base
                        .add(3)
                        .cast::<unsafe extern "system-unwind" fn(node: *mut VSNode) -> c_int>()
                };
                let frame_res = unsafe {
                    *api_ext_base
                        .add(4)
                        .cast::<unsafe extern "system-unwind" fn(frame: *const VSFrame) -> c_int>()
                };
                (API_4_3_NEW_FNS_COUNT, Some(node_res), Some(frame_res))
            }
            _ => {
                return Err(
                    c"Graph: Unsupported VapourSynth API version for graph inspection (requires API 4.2 or 4.3)",
                );
            }
        };

        // SAFETY: When EnableGraphInspection is enabled, the function table extension is guaranteed
        // to be present at the layout offset matching the runtime API version.
        let raw = unsafe { *api_ext_base.add(graph_fns_offset).cast::<RawGraphFns>() };

        Ok(Self {
            function_name: raw.function_name,
            plugin_id: raw.plugin_id,
            plugin_ns: raw.plugin_ns,
            function_arguments: raw.function_arguments,
            get_node_residency,
            get_frame_residency,
        })
    }

    pub(crate) fn function_name(&self, node: *mut VSNode, level: i32) -> *const c_char {
        unsafe { (self.function_name)(node, level) }
    }

    pub(crate) fn plugin_id(&self, node: *mut VSNode, level: i32) -> *const c_char {
        unsafe { (self.plugin_id)(node, level) }
    }

    pub(crate) fn plugin_ns(&self, node: *mut VSNode, level: i32) -> *const c_char {
        unsafe { (self.plugin_ns)(node, level) }
    }

    pub(crate) fn function_arguments(&self, node: *mut VSNode, level: i32) -> *const VSMap {
        unsafe { (self.function_arguments)(node, level) }
    }

    pub(crate) fn get_node_residency(&self, node: *mut VSNode) -> Option<bool> {
        self.get_node_residency.map(|f| unsafe { f(node) == 1 })
    }

    pub(crate) fn get_frame_residency(&self, frame: *const VSFrame) -> Option<bool> {
        self.get_frame_residency.map(|f| unsafe { f(frame) == 1 })
    }
}

#[inline]
pub(crate) const fn get_video_format_id(format: &VSVideoFormat) -> u32 {
    if matches!(format.color_family, VSColorFamily::Undefined) {
        return 0; // VSPresetVideoFormat::None (variable format)
    }
    ((format.color_family as u32) << 28)
        | ((format.sample_type as u32) << 24)
        | ((format.bits_per_sample.cast_unsigned()) << 16)
        | ((format.sub_sampling_w.cast_unsigned()) << 8)
        | (format.sub_sampling_h.cast_unsigned())
}

#[inline]
pub(crate) const fn get_audio_format_id(format: &VSAudioFormat) -> u64 {
    (format.sample_type as u64) << 60
        | (format.bits_per_sample.cast_unsigned() as u64 & 0xFF) << 48
        | (format.channel_layout & 0x0000_FFFF_FFFF_FFFF)
}
