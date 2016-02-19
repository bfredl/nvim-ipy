from __future__ import print_function, division
from functools import partial, wraps
from collections import deque
import os, sys
import json
import re
import neovim

try:
    from jupyter_client import KernelManager
    from jupyter_client.threaded import ThreadedKernelClient
    from jupyter_core.application import JupyterApp
    from jupyter_client.consoleapp import JupyterConsoleApp
    from jupyter_core import version_info
    kind = "Jupyter" # :)
except:
    from IPython.kernel import KernelManager
    from IPython.kernel.threaded import ThreadedKernelClient
    from IPython.core.application import BaseIPythonApplication as JupyterApp
    from IPython.consoleapp import IPythonConsoleApp as JupyterConsoleApp
    from IPython import version_info
    kind = "IPython" # plz upgrade

import greenlet
from traceback import format_exc

from .ansi_code_processor import AnsiCodeProcessor

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
        self._null = open("/dev/null","wb",0)
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
        #TODO: cleanup this (by subclassing kernel_clint or something)
        if self.kernel_manager is not None:
            self.kernel_client = self.kernel_manager.client()
        else:
            self.kernel_client = self.kernel_client_class(
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
        return partial(self.wraps.vim.session.threadsafe_call, getattr(self.wraps, name))

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

    # FIXME: encoding
    def append_outbuf(self, data):
        self.hl_handler.reset_sgr()
        data = strip_ansi.sub('', data)
        lineno = len(self.buf)
        lastline = self.buf[-1]

        txt = lastline + data
        self.buf[-1:] = txt.split("\n") # not splitlines
        for w in self.vim.windows:
            if w.buffer == self.buf:
                w.cursor = [len(self.buf), int(1e9)]
        return lineno

    def append_outbuf_esc(self, data):
        lineno = len(self.buf)-1
        lastline = self.buf[-1]
        colpos = len(lastline)

        textdata = strip_ansi.sub('', data)
        txt = lastline + textdata
        self.buf[-1:] = txt.split("\n") # not splitlines
        for i,line in enumerate(data.split("\n")):
            for chunk in self.hl_handler.split_string(line):
                l = len(chunk)
                bold = self.hl_handler.bold or self.hl_handler.intensity > 0
                color = self.hl_handler.foreground_color
                if color and color > 8: color = None

                if color is not None:
                    name = "IPyFg{}".format(color)
                    if bold: name += "Bold"
                elif bold:
                    name = "IPyBold"
                else:
                    name = None
                if name:
                    self.buf.add_highlight(name, lineno+i, colpos, colpos+l)
                colpos += l
            colpos = 0

        for w in self.vim.windows:
            if w.buffer == self.buf:
                w.cursor = [len(self.buf), int(1e9)]
        return lineno

    # TODO: should cleanly support reconnecting ( cleaning up previous connection)
    def connect(self, argv):
        vim = self.vim

        self.ip_app = JupyterVimApp()
        # messages will be recieved in IPython's event loop threads
        # so use the async self
        self.ip_app.initialize(Async(self), argv)
        self.kc = self.ip_app.kernel_client
        self.km = self.ip_app.kernel_manager
        self.has_connection = True

        reply = self.waitfor(self.kc.kernel_info())
        c = reply['content']
        lang = c['language_info']['name']
        langver = c['language_info']['version']

        try:
            ipy_version = c['ipython_version']
        except KeyError:
            ipy_version = version_info
        vdesc = '.'.join(str(i) for i in ipy_version[:3])
        if len(ipy_version) >= 4 and ipy_version[3] != '':
            vdesc += '-' + ipy_version[3]
        banner = [
                "nvim-ipy: Jupyter shell for Neovim",
                "{} {}".format(kind, vdesc),
                "language: {} {}".format(lang, langver),
                "",
                ]
        self.buf[:0] = banner
        for i in range(len(banner)):
            self.buf.add_highlight('Comment', i)

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
        #vim.command("set ft={}".format(lang))

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
                self.km.restart_kernel(True)
            return

        reply = self.waitfor(self.kc.execute(code,silent=silent))
        content = reply['content']
        payload = content['payload']
        for p in payload:
            if p.get("source") == "page":
                # TODO: if this is long, open separate window
                self.append_outbuf(p['text'])

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
        if not c['found']:
            self.append_outbuf("not found: {}\n".format(o['name']))
            return
        self.append_outbuf("\n")
        self.append_outbuf_esc(c['data']['text/plain']+"\n")

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
                line = self.append_outbuf_esc(u'\n{}{}\n'.format(prompt, sep.join(code)))
                self.buf.add_highlight('IPyIn', line+1, 0, len(prompt))
            elif t in ['pyout', 'execute_result']:
                no = c['execution_count']
                res = c['data']['text/plain']
                prompt = self.prompt_out.format(no)
                line = self.append_outbuf_esc((u'{}{}\n').format(prompt, res.rstrip()))
                self.buf.add_highlight('IPyOut', line, 0, len(prompt))
            elif t in ['pyerr', 'error']:
                #TODO: this should be made language specific
                # as the amt of info in 'traceback' differs
                self.append_outbuf_esc('\n'.join(c['traceback']) + '\n')
            elif t == 'stream':
                #perhaps distinguish stderr using gutter marks?
                self.append_outbuf_esc(c['text'])
            elif t == 'display_data':
                d = c['data']['text/plain']
                self.append_outbuf_esc(d + '\n')
        except Exception as e:
            debug("Couldn't handle iopub message %r: %s", m, format_exc())


    def on_shell_msg(self, m):
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
        self.kc.input(self.vim.funcs.input("(IPy) " + msg["content"]["prompt"]))
