use std::{
    ffi::{CStr, c_void},
    marker::PhantomData,
    panic::RefUnwindSafe,
};

use vapoursynth4_rs::{
    core::CoreRef,
    ffi::VSNode,
    frame::{AudioFrame, Frame, FrameContext, VideoFrame},
    key,
    map::{AppendMode, MapRef, Value},
    node::{ActivationReason, Filter, Node},
};

use crate::inspector::GraphInspector;

pub(crate) trait GraphTarget: RefUnwindSafe {
    type FrameType: Frame;
    const NAME: &'static CStr;
    const ARGS: &'static CStr;
    const CLIP_ERR: &'static CStr;
    const PROP_ERR: &'static CStr;

    fn get_node_ptr(input: &MapRef<'_>) -> Option<*mut VSNode>;
}

pub(crate) struct VideoTarget;

impl GraphTarget for VideoTarget {
    type FrameType = VideoFrame;

    const NAME: &'static CStr = c"VideoGraph";
    const ARGS: &'static CStr = c"clip:vnode;pretty:int:opt;";
    const CLIP_ERR: &'static CStr = c"Graph: Failed to get clip";
    const PROP_ERR: &'static CStr = c"Graph: Failed to set output property";

    fn get_node_ptr(input: &MapRef<'_>) -> Option<*mut VSNode> {
        Some(input.get_video_node(key!(c"clip"), 0).ok()?.as_ptr())
    }
}

pub(crate) struct AudioTarget;

impl GraphTarget for AudioTarget {
    type FrameType = AudioFrame;

    const NAME: &'static CStr = c"AudioGraph";
    const ARGS: &'static CStr = c"clip:anode;pretty:int:opt;";
    const CLIP_ERR: &'static CStr = c"AudioGraph: Failed to get clip";
    const PROP_ERR: &'static CStr = c"AudioGraph: Failed to set output property";

    fn get_node_ptr(input: &MapRef<'_>) -> Option<*mut VSNode> {
        Some(input.get_audio_node(key!(c"clip"), 0).ok()?.as_ptr())
    }
}

pub(crate) struct GraphFilter<T>(PhantomData<T>);

impl<T: GraphTarget> Filter for GraphFilter<T> {
    type Error = &'static CStr;
    type FrameType = T::FrameType;
    type FilterData = ();

    const NAME: &'static CStr = T::NAME;
    const ARGS: &'static CStr = T::ARGS;
    const RETURN_TYPE: &'static CStr = c"json:data;";

    fn create(
        input: MapRef<'_>,
        mut output: MapRef<'_>,
        _data: Option<Box<Self::FilterData>>,
        core: CoreRef<'_>,
    ) -> Result<(), Self::Error> {
        let node_ptr = T::get_node_ptr(&input).ok_or(T::CLIP_ERR)?;
        let pretty = input.get_int(key!(c"pretty"), 0).unwrap_or(0) != 0;
        let inspector = GraphInspector::new(core)?;
        let json = inspector.build_graph(node_ptr, pretty)?;

        output
            .set(key!(c"json"), Value::Utf8(&json), AppendMode::Replace)
            .map_err(|_| T::PROP_ERR)?;
        Ok(())
    }

    fn get_frame(
        &self,
        _n: i32,
        _activation_reason: ActivationReason,
        _frame_data: *mut *mut c_void,
        _ctx: FrameContext,
        _core: CoreRef<'_>,
    ) -> Result<Option<Self::FrameType>, Self::Error> {
        unreachable!("No filter node is registered, get_frame is never called");
    }
}

pub(crate) type VideoGraphFilter = GraphFilter<VideoTarget>;
pub(crate) type AudioGraphFilter = GraphFilter<AudioTarget>;
