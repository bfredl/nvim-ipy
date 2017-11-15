from __future__ import print_function, division
from functools import partial, wraps
from collections import deque
import os, sys
import json
import re
import neovim
from neovim.api import NvimError

from itertools import chain

from jupyter_client import KernelManager
from jupyter_client.threaded import ThreadedKernelClient
from jupyter_core.application import JupyterApp
from jupyter_client.consoleapp import JupyterConsoleApp
from jupyter_core import version_info

import greenlet
from traceback import format_exc

from .ansi_code_processor import AnsiCodeProcessor, NewLineAction, CarriageReturnAction, BackSpaceAction

# from http://serverfault.com/questions/71285/in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file
strip_ansi = re.compile('\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]')

import logging
logger = logging.getLogger(__name__)
error, debug, info, warn = (logger.error, logger.debug, logger.info, logger.warn,)
if 'NVIM_IPY_DEBUG_FILE' in os.environ:
    logfile = os.environ['NVIM_IPY_DEBUG_FILE'].strip()
    logger.addHandler(logging.FileHandler(logfile, 'w'))
    logger.level = logging.DEBUG

class RedirectingKernelManager(KernelManager):
    def _launch_kernel(self, cmd, **b):
        # stdout is used to communicate with nvim, redirect it somewhere else
        nullfile = "/dev/null" if os.name != 'nt' else 'NUL'
        self._null = open(nullfile,"wb",0)
        b['stdout'] = self._null.fileno()
        b['stderr'] = self._null.fileno()
        return super(RedirectingKernelManager, self)._launch_kernel(cmd, **b)

class JupyterVimApp(JupyterApp, JupyterConsoleApp):
    # don't use blocking client; we override call_handlers below
    kernel_client_class = ThreadedKernelClient
    kernel_manager_class = RedirectingKernelManager
    aliases = JupyterConsoleApp.aliases #this the way?
    flags = JupyterConsoleApp.flags
    def init_kernel_client(self):
        #TODO: cleanup this (by subclassing kernel_clinet or something)
        if self.kernel_manager is not None:
            self.kernel_client = self.kernel_manager.client()
        else:
            self.kernel_client = self.kernel_client_class(
                                session=self.session,
                                ip=self.ip,
                                transport=self.transport,
                                shell_port=self.shell_port,
                                iopub_port=self.iopub_port,
                                stdin_port=self.stdin_port,
                                hb_port=self.hb_port,
                                connection_file=self.connection_file,
                                parent=self,
            )
        self.kernel_client.shell_channel.call_handlers = self.target.on_shell_msg
        self.kernel_client.iopub_channel.call_handlers = self.target.on_iopub_msg
        self.kernel_client.stdin_channel.call_handlers = self.target.on_stdin_msg
        self.kernel_client.hb_channel.call_handlers = self.target.on_hb_msg
        self.kernel_client.start_channels()

    def initialize(self, target, argv):
        self.target = target
        super(JupyterVimApp, self).initialize(argv)
        JupyterConsoleApp.initialize(self, argv)


class Async(object):
    """Wrapper that defers all method calls on a plugin object to the event
    loop, given that the object has vim attribute"""
    def __init__(self, wraps):
        self.wraps = wraps

    def __getattr__(self, name):
        return partial(self.wraps.vim.async_call, getattr(self.wraps, name))

class ExclusiveHandler(object):
    """Wrapper for buffering incoming messages from a asynchronous source.

    Wraps an async message handler function and ensures a previous message will
    be completely handled before next messsage is processed. Is used to avoid
    iopub messages being printed out-of-order or even interleaved.
    """
    def __init__(self, handler):
        self.msgs = deque()
        self.handler = handler
        self.is_active = False

    def __call__(self, msg):
        self.msgs.append(msg)
        if not self.is_active:
            self.is_active = True
            while self.msgs:
                self.handler(self.msgs.popleft())
            self.is_active = False

@neovim.plugin
@neovim.encoding(True)
class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim
        self.buf = None
        self.has_connection = False

        self.pending_shell_msgs = {}

        # make sure one message is handled at a time
        self.on_iopub_msg = ExclusiveHandler(self._on_iopub_msg)

    def configure(self):
        #FIXME: rethink the entire configuration interface thing
        # we should use dict notifictaions for runtime settings
        self.do_filetype = self.vim.vars.get("ipy_set_ft", 0)
        self.do_highlight = self.vim.vars.get("ipy_highlight", 1)
        self.max_in = self.vim.vars.get("ipy_truncate_input", 0)
        if self.vim.vars.get("ipy_shortprompt", False):
            self.prompt_in = u"{}: "
            self.prompt_out = u"{}: "
        else:
            self.prompt_in = u"In[{}]: "
            self.prompt_out = u"Out[{}]: "

    def create_outbuf(self):
        vim = self.vim
        if self.buf is not None:
            return
        w0 = vim.current.window
        vim.command(":new")
        buf = vim.current.buffer
        buf.options["swapfile"] = False
        buf.options["buftype"] = "nofile"
        buf.name = "[jupyter]"
        vim.current.window = w0
        self.buf = buf
        self.hl_handler = AnsiCodeProcessor()
        self.hl_handler.bold_text_enabled = True

    def append_outbuf(self, data):
        #self.hl_handler.reset_sgr()
        lineidx = len(self.buf)-1
        lastline = self.buf[-1]

        lines = []
        chunks = []

        #self.hl_handler.actions = []

        for chunk in chain([lastline], self.hl_handler.split_string(data)):
            if self.hl_handler.actions:
                assert len(self.hl_handler.actions) == 1
                a = self.hl_handler.actions[0]
                if isinstance(a, NewLineAction):
                    lines.append(chunks)
                    chunks = []
                elif isinstance(a, CarriageReturnAction):
                    chunks = []
                elif isinstance(a, BackSpaceAction):
                    if chunks:
                        if len(chunks[-1]) > 1:
                            chunks[-1][1] = chunks[-1][1][:-1]
                        else:
                            chunks.pop()
            elif len(chunk) > 0:
                groups = []
                if self.do_highlight:
                    bold = self.hl_handler.bold or self.hl_handler.intensity > 0
                    color = self.hl_handler.foreground_color
                    if color and color > 16: color = None

                    if color is not None:
                        if bold and color < 8:
                            color += 8 # be bright and shiny
                        groups.append("IPyFg{}".format(color))

                    if bold:
                        groups.append("IPyBold")
                chunks.append([groups, chunk])

        lines.append(chunks)
        chunks = []

        #TODO: at least this part should be lua:
        textlines = []
        hls = []
        for i,line in enumerate(lines):
            text = ''.join(c[1] for c in line)
            textlines.append(text)
            colend = 0
            for chunk in line:
                colstart = colend
                colend = colstart + len(chunk[1])
                for hl in chunk[0]:
                    hls.append([hl,lineidx+i,colstart,colend])

        self.buf[-1:] = textlines
        calls = [["nvim_buf_add_highlight", [self.buf, -1]+hl] for hl in hls]
        self.vim.api.call_atomic(calls)

        for w in self.vim.windows:
            if w.buffer == self.buf and w != self.vim.current.window:
                w.cursor = [len(self.buf), int(1e9)]
        return lineidx

    def connect(self, argv):
        vim = self.vim

        has_previous = self.has_connection
        if has_previous:
            # TODO: kill last kernel if we owend it?
            JupyterVimApp.clear_instance()

        self.ip_app = JupyterVimApp.instance()
        if has_previous:
            self.ip_app.connection_file = self.ip_app._new_connection_file()

        # messages will be recieved in Jupyter's event loop threads
        # so use the async self
        self.ip_app.initialize(Async(self), argv)
        self.ip_app.start()
        self.kc = self.ip_app.kernel_client
        self.km = self.ip_app.kernel_manager
        self.has_connection = True

        reply = self.waitfor(self.kc.kernel_info())
        c = reply['content']
        lang = c['language_info']['name']
        langver = c['language_info']['version']

        banner = [ "nvim-ipy: Jupyter shell for Neovim"] if not has_previous else []
        try:
            ipy_version = c['ipython_version']
        except KeyError:
            ipy_version = version_info
        vdesc = '.'.join(str(i) for i in ipy_version[:3])
        if len(ipy_version) >= 4 and ipy_version[3] != '':
            vdesc += '-' + ipy_version[3]
        banner.extend([
                "Jupyter {}".format(vdesc),
                "language: {} {}".format(lang, langver),
                "",
                ])

        if has_previous:
            pos = len(self.buf)
            self.buf.append(banner)
        else:
            pos = 0
            self.buf[:0] = banner
        for i in range(len(banner)):
            self.buf.add_highlight('Comment', pos+i)

        if self.do_filetype:
            # TODO: we might want to wrap this in a sync call
            # to avoid racyness with user interaction
            w0 = vim.current.window
            if vim.current.buffer != self.buf:
                for w in vim.windows:
                    if w.buffer == self.buf:
                        vim.current.window = w
                        break
                else:
                    return #reopen window?

            vim.command("set ft={}".format(lang))

            vim.current.window = w0

    def disp_status(self, status):
        self.vim.vars['ipy_status'] = status

    def handle(self, msg_id, handler):
        self.pending_shell_msgs[msg_id] = handler

    def waitfor(self, msg_id, retval=None):
        #FIXME: add some kind of timeout
        gr = greenlet.getcurrent()
        self.handle(msg_id, gr)
        return gr.parent.switch(retval)

    def ignore(self, msg_id):
        self.handle(msg_id, None)

    @neovim.function("IPyConnect", sync=True)
    def ipy_connect(self, args):
        self.configure()
        # create buffer synchronously, as there is slight
        # racyness in seeing the correct current_buffer otherwise
        self.create_outbuf()
        # 'connect' waits for kernelinfo, and so must be async
        Async(self).connect(args)

    @neovim.function("IPyRun")
    def ipy_run(self, args):
        code = args[0]
        silent = bool(args[1]) if len(args) > 1 else False
        if self.km and not self.km.is_alive():
            choice = int(self.vim.funcs.confirm('Kernel died. Restart?', '&Yes\n&No'))
            if choice == 1:
                if self.km.has_kernel:
                    self.km.restart_kernel(True)
                else:
                    self.km.start_kernel(**self.km._launch_args)
            return

        reply = self.waitfor(self.kc.execute(code,silent=silent))
        content = reply['content']
        payload = content.get('payload',())
        for p in payload:
            if p.get("source") == "page":
                # TODO: if this is long, open separate window
                if 'text' in p:
                    self.append_outbuf(p['text'])
                else:
                    self.append_outbuf(p['data']['text/plain'])

    @neovim.function("IPyDbgWrite", sync=True)
    def ipy_write(self, args):
        self.append_outbuf(args[0])

    @neovim.function("IPyComplete")
    def ipy_complete(self,args):
        line = self.vim.current.line
        #FIXME: (upstream) this sometimes get wrong if
        #completing just after entering insert mode:
        #pos = self.vim.current.buffer.mark(".")[1]+1
        pos = self.vim.funcs.col('.')-1

        reply = self.waitfor(self.kc.complete(line, pos))
        content = reply["content"]
        #TODO: check if position is still valid
        start = content["cursor_start"]+1
        self.vim.funcs.complete(start, content['matches'])

    @neovim.function("IPyOmniFunc", sync=True)
    def ipy_omnifunc(self,args):
        findstart, base = args
        if findstart:
            if not self.has_connection:
                return False
            line = self.vim.current.line
            pos = self.vim.funcs.col('.')-1

            reply = self.waitfor(self.kc.complete(line, pos))
            content = reply["content"]
            start = content["cursor_start"]
            self._matches = content['matches']
            return start
        else:
            return self._matches

    @neovim.function("IPyObjInfo")
    def ipy_objinfo(self, args):
        word, level = args
        #TODO: send entire line
        reply = self.waitfor(self.kc.inspect(word, None, level))

        c = reply['content']
        if c["status"] == "error":
            l = self.append_outbuf("\nerror when inspecting {}: {}\n".format(word, c.get("ename", "")))
            if self.do_highlight:
                self.buf.add_highlight("Error", l+1, 0, -1)
            if "traceback" in c:
                self.append_outbuf('\n'.join(c['traceback'])+"\n")

        elif not c.get('found'):
            l = self.append_outbuf("\nnot found: {}\n".format(word))
            if self.do_highlight:
                self.buf.add_highlight("WarningMsg", l+1, 0, -1)
        else:
            self.append_outbuf("\n"+c['data']['text/plain']+"\n")

    @neovim.function("IPyInterrupt")
    def ipy_interrupt(self, args):
        self.km.interrupt_kernel()

    @neovim.function("IPyTerminate")
    def ipy_terminate(self, args):
        self.km.shutdown_kernel()

    def _on_iopub_msg(self, m):
        #FIXME: figure out the smoothest way to to matchaddpos
        # (from a different window), or just use concealends
        try:
            t = m['header'].get('msg_type',None)
            c = m['content']

            debug('iopub %s: %r', t, c)
            if t == 'status':
                status = c['execution_state']
                self.disp_status(status)
            elif t in ['pyin', 'execute_input']:
                prompt = self.prompt_in.format(c['execution_count'])
                code = c['code'].rstrip().split('\n')
                if self.max_in and len(code) > self.max_in:
                    code = code[:self.max_in] + ['.....']
                sep = '\n'+' '*len(prompt)
                line = self.append_outbuf(u'\n{}{}\n'.format(prompt, sep.join(code)))
                self.buf.add_highlight('IPyIn', line+1, 0, len(prompt))
            elif t in ['pyout', 'execute_result']:
                no = c['execution_count']
                res = c['data']['text/plain']
                prompt = self.prompt_out.format(no)
                line = self.append_outbuf((u'{}{}\n').format(prompt, res.rstrip()))
                self.buf.add_highlight('IPyOut', line, 0, len(prompt))
            elif t in ['pyerr', 'error']:
                #TODO: this should be made language specific
                # as the amt of info in 'traceback' differs
                self.append_outbuf('\n'.join(c['traceback']) + '\n')
            elif t == 'stream':
                #perhaps distinguish stderr using gutter marks?
                self.append_outbuf(c['text'])
            elif t == 'display_data':
                d = c['data']['text/plain']
                self.append_outbuf(d + '\n')
        except Exception as e:
            debug("Couldn't handle iopub message %r: %s", m, format_exc())


    def on_shell_msg(self, m):
        self.last_msg = m
        debug('shell %s: %r', m['msg_type'], m['content'])
        msg_id = m['parent_header']['msg_id']
        try:
            handler = self.pending_shell_msgs.pop(msg_id)
        except KeyError:
            debug('unexpected shell msg: %r', m)
            return
        if isinstance(handler, greenlet.greenlet):
            handler.parent = greenlet.getcurrent()
            handler.switch(m)
        elif handler is not None:
            handler(m)

    #this gets called when heartbeat is lost
    def on_hb_msg(self, time_since):
        self.disp_status("DEAD")

    def on_stdin_msg(self, msg):
        self.last_msg = msg
        try:
            res = self.vim.funcs.input("(IPy) " + msg["content"]["prompt"])
        except NvimError:
            #TODO(nvim) return exceptions precisely
            # for now assume keyboard interrupt
            self.ipy_interrupt([])
            return

        if self.last_msg is msg:
            # from jupyter_console, input should be considered to be interrupted
            # if there was another message
            self.kc.input(res)
