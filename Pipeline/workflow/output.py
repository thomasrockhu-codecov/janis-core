from typing import Dict, Optional, Any

from Pipeline.graph.node import Node, NodeTypes
import cwlgen.cwlgen as cwl
from Pipeline.types.data_types import DataType
from Pipeline.tool.commandtool import ToolOutput, ToolInput


class Output:
    """
        Only catch with output is we infer the type, we don't explicitly define it
    """
    def __init__(self, identifier: str, data_type: Optional[DataType], meta: Any = None,
                 label: str=None, doc: str=None):
        self._identifier: str = identifier
        self.label = label
        self.doc = doc

        self.data_type: Optional[DataType] = data_type
        self.meta = meta

    def id(self) -> str:
        return self._identifier

    def cwl(self, output_source):
        return cwl.WorkflowOutputParameter(
            param_id=self.id(),
            output_source=output_source,
            label=self.label,
            secondary_files=self.data_type.secondary_files(),
            param_format=None,
            streamable=False,
            doc=self.doc,
            param_type=self.data_type.cwl2_type(),
            output_binding=None,
            linkMerge=None
        )


class OutputNode(Node):

    def __init__(self, output: Output):
        self.output = output
        super().__init__(NodeTypes.OUTPUT, output.id())

    def inputs(self) -> Dict[str, ToolInput]:
        return {self.output._identifier: ToolInput("outp", self.output.data_type)}

    def outputs(self) -> Dict[str, ToolOutput]:
        return {}

    def cwl(self):
        source = next(iter(self.connection_map.values())).source()
        return self.output.cwl(source)
