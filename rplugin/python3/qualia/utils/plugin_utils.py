from collections import defaultdict
from os.path import basename
from pathlib import Path
from sys import executable
from time import sleep
from typing import Optional, TYPE_CHECKING

from pynvim import Nvim, NvimError

from qualia.config import NVIM_DEBUG_PIPE, _FZF_LINE_DELIMITER, _TRANSPOSED_FILE_PREFIX
from qualia.config import _FILE_FOLDER
from qualia.models import NodeId, DuplicateNodeException, UncertainNodeChildrenException, View, BufferId, LastSync, \
    LineInfo, KeyNotFoundError
from qualia.utils.common_utils import file_name_to_node_id, logger, exception_traceback
from qualia.database import Database

if TYPE_CHECKING:
    from pynvim.api import Buffer


class PluginUtils:

    def __init__(self, nvim: Nvim, debugging: bool):
        self.nvim = nvim
        self.ide_debugging = nvim.eval('v:servername') == NVIM_DEBUG_PIPE or debugging
        self.highlight_ns = nvim.funcs.nvim_create_namespace("qualia")

        self.changedtick: dict[BufferId, int] = defaultdict(lambda: -1)
        self.undo_seq: dict[BufferId, int] = {}
        self.buffer_last_sync: dict[BufferId, LastSync] = defaultdict(LastSync)
        self.last_git_sync = 0.
        self.enabled: bool = True

    def print_message(self, *args: object):
        text = ' - '.join([str(text) for text in args])
        logger.debug(text)
        self.nvim.out_write(text + '\n')

    def replace_with_file(self, filepath: str, replace_buffer: bool) -> None:
        command = f"let g:qualia_last_buffer=bufnr('%') |  silent edit {filepath} | normal lh"  # wiggle closes FZF popup
        # silent!
        if replace_buffer:
            command += " | bdelete g:qualia_last_buffer"
        try:
            self.nvim.command(command)
        except NvimError as e:
            if "ATTENTION" not in str(e):
                raise e

    def navigate_node(self, node_id: NodeId, replace_buffer: bool) -> None:
        transposed = self.buffer_transposed(self.nvim.current.buffer.name)
        filepath = self.node_id_to_filepath(node_id, transposed)
        if self.nvim.current.buffer.name != filepath:
            self.replace_with_file(filepath, replace_buffer)

    def process_filepath(self, buffer_name: str, db: Database, view) -> tuple[bool, bool, NodeId]:
        switched_buffer = False
        try:
            main_id, transposed = self.resolve_main_id(buffer_name, db)
        except ValueError:
            main_id, transposed = self.navigate_root_node(buffer_name, db)
            switched_buffer = True
        if view and main_id != view.main_id:
            self.navigate_node(view.main_id, True)
            switched_buffer = True
        return switched_buffer, transposed, main_id

    def navigate_root_node(self, buffer_name: str, db: Database) -> tuple[NodeId, bool]:
        transposed = self.buffer_transposed(buffer_name)
        root_id = db.get_root_id()
        self.replace_with_file(self.node_id_to_filepath(root_id, transposed), True)
        # self.print_message("Redirecting to root node")
        return root_id, transposed

    def current_buffer_id(self) -> Optional[BufferId]:
        buffer_number: int = self.nvim.current.buffer.number
        try:
            file_path = self.nvim.eval("resolve(expand('%:p'))")
        except OSError:
            return None
        else:
            return buffer_number, Path(file_path).as_posix()

    def current_line_number(self) -> int:
        return self.nvim.funcs.line('.') - 1

    def handle_duplicate_node(self, buffer, exp):
        # type: (Buffer, DuplicateNodeException)->None
        self.nvim.command("set nowrite")
        self.print_message(
            f"Duplicate siblings at lines {', '.join([str(first_line) for first_line, _ in exp.line_ranges])}")
        for node_locs in exp.line_ranges:
            for line_num in range(node_locs[0], node_locs[1]):
                self.highlight_line(buffer.number, line_num)

    def highlight_line(self, buffer_number: int, line_num: int) -> None:
        self.nvim.funcs.nvim_buf_add_highlight(buffer_number, self.highlight_ns, "ErrorMsg", line_num, 0, -1)

    def handle_uncertain_node_descendant(self, buffer, exp, last_sync):
        # type:(Buffer, UncertainNodeChildrenException, LastSync) -> bool
        self.nvim.command("set nowrite")
        start_line_num, end_line_num = exp.line_range
        for line_num in range(start_line_num, min(end_line_num, start_line_num + 50)):
            self.highlight_line(buffer.number, line_num)
        choice = self.nvim.funcs.confirm("Uncertain state", "&Pause parsing\n&Continue", 1)
        if choice == 2:
            last_sync.pop_data(exp.node_id)
            return True
        else:
            self.enabled = False
            return False

    def delete_highlights(self, buffer_numer) -> None:
        self.nvim.funcs.nvim_buf_clear_namespace(buffer_numer, self.highlight_ns, 0, -1)

    def node_ancestory_info(self, line_num: int, level_count: int) -> list[LineInfo]:
        buffer_id = self.current_buffer_id()
        assert buffer_id is not None and level_count > 0
        line_data = self.buffer_last_sync[buffer_id].line_info

        error_msg = f"Line info not found {self.buffer_last_sync=} {line_data=} {line_num=} {buffer_id=} {level_count}"
        if line_data is None:
            raise Exception(error_msg)

        info_list = []
        last_level = float("inf")
        for line_number in range(line_num, -1, -1):
            if line_number in line_data:
                cur_level = line_data[line_number].nested_level
                logger.debug(cur_level)
                if cur_level < last_level:
                    logger.debug("HEre")
                    info_list.append(line_data[line_number])
                    last_level = cur_level
                    level_count -= 1
                    if level_count == 0:
                        break

        assert level_count == 0, (info_list, error_msg)

        return info_list

    def line_info(self, line_num: int) -> LineInfo:
        return self.node_ancestory_info(line_num, 1)[0]

    def line_node_view(self, line_num) -> View:
        line_info = self.line_info(line_num)
        node_id = line_info.node_id
        view = View(node_id, line_info.parent_view.sub_tree[node_id] if line_info.parent_view.sub_tree else {})
        return view

    @staticmethod
    def buffer_transposed(buffer_name: str) -> bool:
        return basename(buffer_name)[0] == _TRANSPOSED_FILE_PREFIX

    # @staticmethod
    def node_id_to_filepath(self, node_id: NodeId, transposed) -> str:
        file_name = node_id + ".q.md"
        if transposed:
            file_name = _TRANSPOSED_FILE_PREFIX + file_name
        return _FILE_FOLDER.joinpath(file_name).as_posix()

    @staticmethod
    def resolve_main_id(buffer_name: str, db: Database) -> tuple[NodeId, bool]:
        file_name = basename(buffer_name)
        transposed = PluginUtils.buffer_transposed(buffer_name)
        if transposed:
            file_name = file_name[1:]
        main_id = file_name_to_node_id(file_name, '.q.md')
        try:
            db.get_node_content_lines(main_id)
        except KeyNotFoundError:
            raise ValueError(buffer_name)
        return main_id, transposed

    def should_continue(self, force: bool) -> bool:
        in_normal_mode = self.nvim.funcs.mode() == 'n'
        if not force and self.ide_debugging:
            sleep(0.1)
            if not in_normal_mode:
                return False

        if not (self.enabled and (force or in_normal_mode) and self.nvim.current.buffer.name.endswith(".q.md")):
            return False

        undotree = self.nvim.funcs.undotree()

        cur_undo_seq = undotree["seq_cur"]

        if (self.ide_debugging and undotree["synced"] == 0) or (cur_undo_seq < undotree["seq_last"]):
            return False

        buffer_id = self.current_buffer_id()
        if buffer_id is None:
            return False
        if buffer_id in self.undo_seq:
            last_processed_undo_seq = self.undo_seq[buffer_id]
            if cur_undo_seq < last_processed_undo_seq or (cur_undo_seq == last_processed_undo_seq and not force):
                return False
            else:
                for undo_entry in reversed(undotree['entries']):
                    if cur_undo_seq in undo_entry:
                        if 'alt' in undo_entry:
                            self.buffer_last_sync.pop(buffer_id)
                        break
        self.undo_seq[buffer_id] = cur_undo_seq

        # Undo changes changedtick so check that before to pop last_sync
        try:
            changedtick = self.nvim.eval("b:changedtick")
        except OSError as e:
            self.print_message(exception_traceback(e))
        else:
            if not force and changedtick == self.changedtick[buffer_id]:
                return False
            else:
                self.changedtick[buffer_id] = changedtick

        return True

    fzf_sink_command = "NodeFzfSink"

    def fzf_run(self, fzf_lines: list[str], query: str) -> None:
        self.nvim.call("fzf#run",
                       {'source': fzf_lines, 'sink': self.fzf_sink_command, 'window': {'width': 0.95, 'height': 0.98},
                        'options': ['--delimiter', _FZF_LINE_DELIMITER, '--with-nth', '2..', '--query', query,
                                    '--preview', executable + " " + Path(__file__).parent.parent.joinpath(
                                'services/preview.py').as_posix() + " {1} 1",
                                    '--preview-window', ":wrap"]})


def get_orphan_node_ids(db: Database) -> list[NodeId]:
    root_id = db.get_root_id()
    visited_node_ids = {root_id}

    node_stack = [root_id]
    while node_stack:
        node_id = node_stack.pop()
        node_children_ids = db.get_node_descendants(node_id, False, True)
        if node_children_ids:
            node_stack.extend((child_id for child_id in node_children_ids if child_id not in visited_node_ids))
            visited_node_ids.update(node_children_ids)
    orphan_node_ids = [node_id for node_id in db.get_node_ids() if node_id not in visited_node_ids]
    return orphan_node_ids