use std::ffi::{CStr, c_int};

use vapoursynth4_rs::{
    VAPOURSYNTH_API_VERSION,
    core::CoreHandle,
    ffi::{VSAudioFormat, VSColorFamily, VSCoreCreationFlags, VSVideoFormat, vs_make_version},
};

// The graph inspection functions are experimental and sit at the end of `VSAPI`.
// When a new API minor version adds functions, they are inserted before the graph block,
const _: () = assert!(
    VAPOURSYNTH_API_VERSION == vs_make_version(4, 3),
    "graph inspection layout was only checked against VapourSynth API 4.3"
);

/// Checks that the graph inspection functions in the core's `VSAPI` table can be used.
pub(crate) fn ensure_graph_support(core: &CoreHandle) -> Result<(), &'static CStr> {
    let info = core.get_info2();
    let is_inspection_enabled =
        (info.creation_flags & (VSCoreCreationFlags::EnableGraphInspection as c_int)) != 0;
    if !is_inspection_enabled {
        return Err(c"Graph: EnableGraphInspection is not enabled on this core");
    }

    // SAFETY: `getAPIVersion` is part of the base API and is always present.
    let runtime_api = unsafe { (core.api().getAPIVersion)() };
    if runtime_api != VAPOURSYNTH_API_VERSION {
        return Err(
            c"Graph: Unsupported VapourSynth API version for graph inspection (requires API 4.3)",
        );
    }

    Ok(())
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
