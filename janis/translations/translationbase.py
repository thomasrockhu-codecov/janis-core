from abc import ABC, abstractmethod
import os
from typing import Tuple, List, Dict

from janis.translations.exportpath import ExportPathKeywords
from janis.utils.logger import Logger
from janis.workflow.input import Input


class TranslatorBase(ABC):
    """
    So you're thinking about adding a new translation :)

    This class will hopefully give you a pretty good indication
    on what's required to add a new translation, however what I
    can't fully talk about are all the concepts.

    To add a new translation, you should understand at least these
    workflow and janis concepts:
        - inputs
        - outputs
        - steps + tools
        - secondary files
        - command line binding of tools
            - position, quoted
        - selectors
            - input selectors
            - wildcard glob selectors
            - cpu and memory selectors
        - propagated resource overrides

    I'd ask that you keep your function sizes small and direct,
    and then write unit tests to cover each component of the translation
    and then an integration test of the whole translation on the related workflows.

    You can find these in /janis/tests/test_translation_*.py)
    """

    def __init__(self, name):
        self.name = name

    def translate(self, workflow, to_console=True, with_docker=True, with_resource_overrides=False, to_disk=False,
             export_path=ExportPathKeywords.default, write_inputs_file=False, should_validate=False,
             should_zip=True, merge_resources=False, hints=None, allow_null_if_not_optional=True):

        self.validate_inputs(workflow._inputs, allow_null_if_not_optional)

        tr_wf, tr_tools = self.translate_workflow(
            workflow,
            with_docker=with_docker,
            with_resource_overrides=with_resource_overrides
        )
        tr_inp = self.build_inputs_file(workflow, recursive=False, merge_resources=merge_resources, hints=hints)
        tr_res = self.build_resources_input(workflow, hints)

        str_wf = self.stringify_translated_workflow(tr_wf)
        str_inp = self.stringify_translated_inputs(tr_inp)
        str_tools = [
            ("/tools/" + self.tool_filename(t), self.stringify_translated_workflow(tr_tools[t]))
            for t in tr_tools
        ]
        str_resources = self.stringify_translated_inputs(tr_res)

        if to_console:
            print("=== WORKFLOW ===")
            print(str_wf)
            print("\n=== TOOLS ===")
            [print(f":: {t[0]} ::\n" + t[1]) for t in str_tools]
            print("\n=== INPUTS ===")
            print(str_inp)
            if not merge_resources and with_resource_overrides:
                print("\n=== RESOURCES ===")
                print(str_resources)

        d = ExportPathKeywords.resolve(export_path, workflow_spec=self.name, workflow_name=workflow.id())

        fn_workflow = self.workflow_filename(workflow)
        fn_inputs = self.inputs_filename(workflow)
        fn_resources = self.resources_filename(workflow)

        if write_inputs_file:
            if not os.path.isdir(d):
                os.makedirs(d)

            with open(d + fn_inputs, "w+") as f:
                Logger.log(f"Writing {fn_inputs} to disk")
                f.write(str_inp)
                Logger.log(f"Written {fn_inputs} to disk")
        else:
            Logger.log("Skipping writing input (yaml) job file")

        if to_disk:

            if not os.path.isdir(d + "tools/"):
                os.makedirs(d + "tools/")

            with open(d + fn_workflow, "w+") as wf:
                Logger.log(f"Writing {fn_workflow} to disk")
                wf.write(str_wf)
                Logger.log(f"Wrote {fn_workflow}  to disk")

            for (fn_tool, str_tool) in str_tools:
                with open(d + fn_tool, "w+") as cwl:
                    Logger.log(f"Writing {fn_tool} to disk")
                    cwl.write(str_tool)
                    Logger.log(f"Written {fn_tool} to disk")

            if not merge_resources and with_resource_overrides:
                print("\n=== RESOURCES ===")
                with open(d + fn_resources, "w+") as wf:
                    Logger.log(f"Writing {fn_resources} to disk")
                    wf.write(str_wf)
                    Logger.log(f"Wrote {fn_resources}  to disk")
                print(str_resources)

            import subprocess
            if should_zip:
                Logger.info("Zipping tools")
                os.chdir(d)

                zip_result = subprocess.run(["zip", "-r", "tools.zip", "tools/"])
                if zip_result.returncode == 0:
                    Logger.info("Zipped tools")
                else:
                    Logger.critical(zip_result.stderr)

            if should_validate:
                os.chdir(d)

                Logger.info(f"Validating outputted {self.name}")

                enved_vcs = [(os.getenv(x[1:]) if x.startswith("$") else x)
                                 for x in self.validate_command_for(fn_workflow, fn_inputs, "tools/", "tools.zip")]

                cwltool_result = subprocess.run(enved_vcs)
                if cwltool_result.returncode == 0:
                    Logger.info("Exported workflow is valid CWL.")
                else:
                    Logger.critical(cwltool_result.stderr)

        return str_wf, str_inp, str_tools

    @classmethod
    def validate_inputs(cls, inputs: List[Input], allow_null_if_optional):
        invalid = [i for i in inputs if i.validate_value(allow_null_if_not_optional=allow_null_if_optional)]
        if len(invalid) == 0: return True
        raise TypeError("Couldn't validate inputs: ", ", ".join(i.id() for i in invalid))

    @classmethod
    @abstractmethod
    def translate_workflow(cls, workflow, with_docker=True, with_resource_overrides=False) \
            -> Tuple[any, Dict[str, any]]:
        pass

    @classmethod
    @abstractmethod
    def translate_tool(cls, tool, with_docker, with_resource_overrides=False):
        pass

    @classmethod
    @abstractmethod
    def build_inputs_file(cls, workflow, recursive=False, merge_resources=False, hints=None) -> Dict[str, any]:
        pass

    @classmethod
    @abstractmethod
    def build_resources_input(cls, workflow, hints):
        pass

    @staticmethod
    def inp_can_be_skipped(inp: Input):
        return inp.value is None and not inp.include_in_inputs_file_if_none and (inp.data_type.optional or inp.default is not None)

    # STRINGIFY

    @staticmethod
    @abstractmethod
    def stringify_translated_workflow(wf):
        pass

    @staticmethod
    @abstractmethod
    def stringify_translated_tool(tool):
        pass

    @staticmethod
    @abstractmethod
    def stringify_translated_inputs(inputs):
        pass

    # OUTPUTS

    @staticmethod
    @abstractmethod
    def workflow_filename(self):
        pass

    @staticmethod
    @abstractmethod
    def inputs_filename(workflow):
        pass

    @staticmethod
    @abstractmethod
    def tool_filename(tool):
        pass

    @staticmethod
    def dependencies_filename(workflow):
        return "tools.zip"

    @staticmethod
    @abstractmethod
    def resources_filename(workflow):
        pass

    # VALIDATION

    @staticmethod
    @abstractmethod
    def validate_command_for(wfpath, inppath, tools_dir_path, tools_zip_path):
        pass

