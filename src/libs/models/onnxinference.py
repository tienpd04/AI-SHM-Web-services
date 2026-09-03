from typing import TYPE_CHECKING, Any, Dict, List, Literal, Sequence

if TYPE_CHECKING:
    from numpy.typing import NDArray
from os import PathLike

import onnxruntime as ort

from .meta import InferenceModelMeta


class ONNXInference(InferenceModelMeta):
    _ort_session: ort.InferenceSession

    DEFAULT_PROVIDER = ("CPUExecutionProvider",)

    def __init__(
        self,
        path_or_bytes: str | bytes | PathLike,
        *,
        execution_mode: Literal["sequence", "parallel"] = "sequence",
        limit_mem_gpu_GB: int | float = -1,
        use_tf32: bool = True,
        enable_mem_pattern: bool = True,
        enable_cpu_mem_arena: bool = True,
        intra_op_num_threads: int = 0,
        inter_op_num_threads: int = 1
    ):
        if limit_mem_gpu_GB <= 0 or ort.get_all_providers() == self.DEFAULT_PROVIDER:
            providers = self.DEFAULT_PROVIDER
            self.device = "cpu"
        else:
            self.device = "cuda"
            providers = [
                (
                    "CUDAExecutionProvider",
                    {
                        "device_id": 0,
                        "arena_extend_strategy": "kNextPowerOfTwo",
                        "gpu_mem_limit": int(limit_mem_gpu_GB * 1024 * 1024 * 1024),
                        "cudnn_conv_algo_search": "EXHAUSTIVE",
                        "do_copy_in_default_stream": True,
                        "use_tf32": use_tf32,
                    },
                ),
                *self.DEFAULT_PROVIDER,
            ]

        sess_options = ort.SessionOptions()
        if execution_mode == "parallel":
            sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
        sess_options.enable_mem_pattern = enable_mem_pattern
        sess_options.enable_cpu_mem_arena = enable_cpu_mem_arena
        sess_options.intra_op_num_threads = intra_op_num_threads
        sess_options.inter_op_num_threads = inter_op_num_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._ort_session = ort.InferenceSession(
            path_or_bytes, sess_options=sess_options, providers=providers)
        self._set_io()

    def _set_io(self):
        # Using for subclass
        pass

    @property
    def ort_session(self) -> ort.InferenceSession:
        return self._ort_session

    @property
    def input_info(self) -> Sequence[ort.NodeArg]:
        return self.ort_session.get_inputs()

    @property
    def output_info(self) -> Sequence[ort.NodeArg]:
        return self.ort_session.get_outputs()

    def inference(self, output_names: List[str] | None, inputs: Dict[str, Any]) -> List['NDArray']:
        if self.device == 'cpu':
            return self.ort_session.run(output_names, inputs)
        io_binding = self.ort_session.io_binding()

        for ort_input_name, ort_input in inputs.items():
            io_binding.bind_cpu_input(ort_input_name, ort_input)

        for ort_out_name in output_names:
            io_binding.bind_output(ort_out_name, self.device)

        self.ort_session.run_with_iobinding(io_binding)
        preds = io_binding.copy_outputs_to_cpu()
        io_binding.clear_binding_inputs()
        io_binding.clear_binding_outputs()
        del io_binding

        return preds

    def health(self) -> bool:
        return self._ort_session is not None


class SingleInputOnnxInference(ONNXInference):
    def _set_io(self):
        self._input_name = self.input_info[0].name
        self._output_names = tuple([o.name for o in self.output_info])

    @property
    def input_name(self) -> str:
        return self._input_name

    @property
    def output_names(self) -> tuple[str, ...]:
        return self._output_names

    def inference(self, input_tensor: 'NDArray') -> list['NDArray']:
        return super().inference(self._output_names, {self._input_name: input_tensor})


class SingleInputOutputOnnxInference(SingleInputOnnxInference):
    def _set_io(self):
        self._input_name = self.input_info[0].name
        self._output_names = (self.output_info[0].name,)
