mod api;
mod filter;
mod inspector;
mod model;
use envparse::parse_env;
use filter::{AudioGraphFilter, VideoGraphFilter};
use vapoursynth4_rs::declare_plugin;

const PLUGIN_VERSION: (u16, u16) = (
    parse_env!("GRAPH_VERSION_MAJOR" as u16 else 0),
    parse_env!("GRAPH_VERSION_MINOR" as u16 else 0),
);

declare_plugin!(
    c"varde.graph",
    c"graph",
    c"Graph Inspection.",
    PLUGIN_VERSION,
    VAPOURSYNTH_API_VERSION,
    0,
    (VideoGraphFilter, None),
    (AudioGraphFilter, None)
);
