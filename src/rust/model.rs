use std::collections::BTreeMap;

use serde::Serialize;

#[derive(Serialize)]
pub(crate) struct GraphOutput {
    pub(crate) root_id: String,
    pub(crate) nodes: Vec<NodeEntry>,
    pub(crate) edges: Vec<EdgeEntry>,
}

#[derive(Serialize)]
pub(crate) struct NodeEntry {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) filter_mode: i32,
    pub(crate) processing_time_ns: i64,
    pub(crate) media_info: MediaInfo,
    pub(crate) call_stack: Vec<CallFrame>,
}

#[derive(Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub(crate) enum MediaInfo {
    Video {
        format: String,
        width: i32,
        height: i32,
        fps_num: i64,
        fps_den: i64,
        num_frames: i32,
    },
    Audio {
        format: String,
        sample_rate: i32,
        bits_per_sample: i32,
        num_channels: i32,
        channel_layout: u64,
        num_samples: i64,
        num_frames: i32,
    },
}

#[derive(Serialize)]
pub(crate) struct CallFrame {
    pub(crate) level: i32,
    pub(crate) frame_id: String,
    pub(crate) plugin_id: String,
    pub(crate) plugin_ns: String,
    pub(crate) function: String,
    pub(crate) arguments: BTreeMap<String, serde_json::Value>,
}

#[derive(Serialize)]
pub(crate) struct EdgeEntry {
    pub(crate) from: String,
    pub(crate) to: String,
    pub(crate) pattern: i32,
}
