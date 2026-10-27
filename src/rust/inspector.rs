use std::{
    collections::{BTreeMap, HashSet},
    ffi::{CStr, c_char, c_int},
    slice,
};

use serde_json::{Number, Value};
use vapoursynth4_rs::{
    api::Api,
    core::CoreRef,
    ffi::{VSDataTypeHint, VSMap, VSMapPropertyError, VSMediaType, VSNode, VSPropertyType},
};

use crate::{
    api::GraphApiFns,
    model::{CallFrame, EdgeEntry, GraphOutput, MediaInfo, NodeEntry},
};

pub(crate) struct GraphInspector {
    api: Api,
    graph_api: GraphApiFns,
}

impl GraphInspector {
    pub(crate) fn new(core: CoreRef<'_>) -> Result<Self, &'static CStr> {
        let graph_api = GraphApiFns::resolve(core)?;
        Ok(Self {
            api: core.api(),
            graph_api,
        })
    }

    /// Recursively traverses the node dependency graph and serializes it to JSON.
    pub(crate) fn build_graph(
        &self,
        root_node: *mut VSNode,
        pretty: bool,
    ) -> Result<String, &'static CStr> {
        let mut stack = vec![root_node];
        let mut visited = HashSet::new();
        let mut nodes = Vec::new();
        let mut edges = Vec::new();

        while let Some(n) = stack.pop() {
            if !visited.insert(n) {
                continue;
            }

            let this_id = node_id(n);

            // SAFETY: `n` is a valid `VSNode` pointer visited during graph traversal.
            let (name, filter_mode, processing_time_ns) = unsafe {
                (
                    cstr_to_string((self.api.getNodeName)(n)),
                    (self.api.getNodeFilterMode)(n) as i32,
                    (self.api.getNodeProcessingTime)(n, 0),
                )
            };
            let media_info = self.extract_media_info(n);
            let call_stack = self.extract_call_stack(n);

            // SAFETY: `n` is valid. We iterate over its dependencies.
            unsafe {
                let num_deps = (self.api.getNumNodeDependencies)(n);
                for i in 0..num_deps {
                    let dep_ptr = (self.api.getNodeDependency)(n, i);
                    if let Some(dep) = dep_ptr.as_ref() {
                        edges.push(EdgeEntry {
                            from: node_id(dep.source),
                            to: this_id.clone(),
                            pattern: dep.request_pattern as i32,
                        });
                        stack.push(dep.source);
                    }
                }
            }

            nodes.push(NodeEntry {
                id: this_id,
                name,
                filter_mode,
                processing_time_ns,
                media_info,
                call_stack,
            });
        }

        let graph = GraphOutput {
            root_id: node_id(root_node),
            nodes,
            edges,
        };

        let serializer = if pretty {
            serde_json::to_string_pretty
        } else {
            serde_json::to_string
        };
        serializer(&graph).map_err(|_| c"Graph: Failed to serialize JSON")
    }

    /// Extracts video or audio media information from the node.
    fn extract_media_info(&self, node: *mut VSNode) -> MediaInfo {
        // SAFETY: caller guarantees `node` is valid.
        unsafe {
            match (self.api.getNodeType)(node) {
                VSMediaType::Video => {
                    let vi = &*(self.api.getVideoInfo)(node);
                    let format =
                        query_format_name(&raw const vi.format, self.api.getVideoFormatName);
                    MediaInfo::Video {
                        format,
                        width: vi.width,
                        height: vi.height,
                        fps_num: vi.fps_num,
                        fps_den: vi.fps_den,
                        num_frames: vi.num_frames,
                    }
                }
                VSMediaType::Audio => {
                    let ai = &*(self.api.getAudioInfo)(node);
                    let format =
                        query_format_name(&raw const ai.format, self.api.getAudioFormatName);
                    MediaInfo::Audio {
                        format,
                        sample_rate: ai.sample_rate,
                        bits_per_sample: ai.format.bits_per_sample,
                        num_channels: ai.format.num_channels,
                        channel_layout: ai.format.channel_layout,
                        num_samples: ai.num_samples,
                        num_frames: ai.num_frames,
                    }
                }
            }
        }
    }

    /// Extracts call stack frames for the given node.
    fn extract_call_stack(&self, node: *mut VSNode) -> Vec<CallFrame> {
        let mut stack = Vec::new();
        for level in 0..c_int::MAX {
            // SAFETY: caller guarantees `node` is valid.
            let Some((args_ptr, plugin_id, plugin_ns, function)) = (unsafe {
                let args = (self.graph_api.function_arguments)(node, level);
                (!args.is_null()).then(|| {
                    (
                        args,
                        cstr_to_string((self.graph_api.plugin_id)(node, level)),
                        cstr_to_string((self.graph_api.plugin_ns)(node, level)),
                        cstr_to_string((self.graph_api.function_name)(node, level)),
                    )
                })
            }) else {
                break;
            };

            let arguments = self.serialize_vsmap(args_ptr);
            stack.push(CallFrame {
                level,
                frame_id: frame_id(args_ptr),
                plugin_id,
                plugin_ns,
                function,
                arguments,
            });
        }
        stack
    }

    /// Serializes a `VapourSynth` map to a JSON key-value object.
    fn serialize_vsmap(&self, map: *const VSMap) -> BTreeMap<String, Value> {
        let Some(raw_map) = RawMap::from_ptr(map, &self.api) else {
            return BTreeMap::new();
        };
        raw_map.to_json_map()
    }
}

struct RawMap<'a> {
    ptr: *const VSMap,
    api: &'a Api,
}

impl<'a> RawMap<'a> {
    fn from_ptr(ptr: *const VSMap, api: &'a Api) -> Option<Self> {
        (!ptr.is_null()).then_some(Self { ptr, api })
    }

    fn num_keys(&self) -> i32 {
        // SAFETY: `self.ptr` is valid and non-null.
        unsafe { (self.api.mapNumKeys)(self.ptr) }
    }

    fn get_key(&self, index: i32) -> Option<&'a CStr> {
        // SAFETY: `self.ptr` is valid.
        let ptr = unsafe { (self.api.mapGetKey)(self.ptr, index) };
        (!ptr.is_null()).then(|| {
            // SAFETY: `mapGetKey` returns a valid null-terminated C string with map lifetime.
            unsafe { CStr::from_ptr(ptr) }
        })
    }

    fn num_elements(&self, key: &CStr) -> i32 {
        // SAFETY: `self.ptr` and `key` are valid pointers.
        unsafe { (self.api.mapNumElements)(self.ptr, key.as_ptr()) }
    }

    fn prop_type(&self, key: &CStr) -> VSPropertyType {
        // SAFETY: `self.ptr` and `key` are valid pointers.
        unsafe { (self.api.mapGetType)(self.ptr, key.as_ptr()) }
    }

    fn get_int(&self, key: &CStr, index: i32) -> i64 {
        let mut err = VSMapPropertyError::Success;
        // SAFETY: `self.ptr` and `key` are valid pointers.
        unsafe { (self.api.mapGetInt)(self.ptr, key.as_ptr(), index, &raw mut err) }
    }

    fn get_float(&self, key: &CStr, index: i32) -> f64 {
        let mut err = VSMapPropertyError::Success;
        // SAFETY: `self.ptr` and `key` are valid pointers.
        unsafe { (self.api.mapGetFloat)(self.ptr, key.as_ptr(), index, &raw mut err) }
    }

    fn get_data(&self, key: &CStr, index: i32) -> (VSDataTypeHint, &[u8]) {
        let mut err = VSMapPropertyError::Success;
        let key_ptr = key.as_ptr();
        // SAFETY: `self.ptr` and `key_ptr` are valid pointers.
        unsafe {
            let hint = (self.api.mapGetDataTypeHint)(self.ptr, key_ptr, index, &raw mut err);
            let size = (self.api.mapGetDataSize)(self.ptr, key_ptr, index, &raw mut err);
            let data_ptr = (self.api.mapGetData)(self.ptr, key_ptr, index, &raw mut err);
            let bytes = if data_ptr.is_null() || size <= 0 {
                &[]
            } else {
                slice::from_raw_parts(data_ptr.cast::<u8>(), size as usize)
            };
            (hint, bytes)
        }
    }

    fn get_node_id(&self, key: &CStr, index: i32) -> String {
        let mut err = VSMapPropertyError::Success;
        // SAFETY: `self.ptr` and `key` are valid pointers.
        unsafe {
            let node_ptr = (self.api.mapGetNode)(self.ptr, key.as_ptr(), index, &raw mut err);
            let id = node_id(node_ptr);
            (self.api.freeNode)(node_ptr);
            id
        }
    }

    fn to_json_map(&self) -> BTreeMap<String, Value> {
        let mut out = BTreeMap::new();
        let num_keys = self.num_keys();

        for i in 0..num_keys {
            let Some(key) = self.get_key(i) else {
                continue;
            };

            let num_elems = self.num_elements(key);
            let prop_type = self.prop_type(key);

            let value = match num_elems {
                ..=0 => Value::Array(Vec::new()),
                1 => self.serialize_element(key, prop_type, 0),
                n => {
                    let arr = (0..n)
                        .map(|j| self.serialize_element(key, prop_type, j))
                        .collect();
                    Value::Array(arr)
                }
            };

            out.insert(key.to_string_lossy().into_owned(), value);
        }

        out
    }

    fn serialize_element(&self, key: &CStr, prop_type: VSPropertyType, index: i32) -> Value {
        match prop_type {
            VSPropertyType::Int => Value::Number(self.get_int(key, index).into()),
            VSPropertyType::Float => {
                Number::from_f64(self.get_float(key, index)).map_or(Value::Null, Value::Number)
            }
            VSPropertyType::Data => {
                let (hint, bytes) = self.get_data(key, index);
                let is_printable = match hint {
                    VSDataTypeHint::Utf8 => true,
                    VSDataTypeHint::Unknown => bytes.len() < 200 && is_ascii_printable(bytes),
                    VSDataTypeHint::Binary => false,
                };

                if is_printable && let Ok(s) = std::str::from_utf8(bytes) {
                    Value::String(s.to_owned())
                } else {
                    Value::String(format!("<binary: {} bytes>", bytes.len()))
                }
            }
            VSPropertyType::VideoNode | VSPropertyType::AudioNode => {
                Value::String(self.get_node_id(key, index))
            }
            VSPropertyType::VideoFrame => Value::String("<vframe>".to_owned()),
            VSPropertyType::AudioFrame => Value::String("<aframe>".to_owned()),
            VSPropertyType::Function => Value::String("<func>".to_owned()),
            VSPropertyType::Unset => Value::Null,
        }
    }
}

fn node_id(node: *const VSNode) -> String {
    format!("node_{}", node.addr())
}

fn frame_id(args: *const VSMap) -> String {
    format!("frame_{}", args.addr())
}

/// Converts a nullable C string pointer into an owned `String`.
/// Returns an empty string if `ptr` is null.
///
/// # Safety
/// If non-null, `ptr` must point to a valid null-terminated C string.
fn cstr_to_string(ptr: *const c_char) -> String {
    if ptr.is_null() {
        String::new()
    } else {
        // SAFETY: caller guarantees `ptr` points to a valid null-terminated C string.
        unsafe { CStr::from_ptr(ptr) }
            .to_string_lossy()
            .into_owned()
    }
}

fn is_ascii_printable(bytes: &[u8]) -> bool {
    bytes.iter().all(|&b| (b' '..=b'~').contains(&b))
}

/// Queries the name of a video or audio format using the provided FFI getter.
///
/// # Safety
/// `format` must be a valid pointer expected by `get_name`.
fn query_format_name<T>(
    format: *const T,
    get_name: unsafe extern "system-unwind" fn(*const T, *mut c_char) -> c_int,
) -> String {
    let mut buf = [0; 32];
    // SAFETY: caller guarantees `format` is valid, and `buf` is a stack buffer of size 32.
    let ok = unsafe { get_name(format, buf.as_mut_ptr()) } != 0;
    if ok {
        cstr_to_string(buf.as_ptr())
    } else {
        "Undefined".to_owned()
    }
}
