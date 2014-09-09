from __future__ import print_function, division
from threading import Thread
from time import sleep
import os, sys
import json
import re
import neovim
import IPython
from IPython.kernel import KernelManager, find_connection_file
from IPython.core.application import BaseIPythonApplication
from IPython.consoleapp import IPythonConsoleApp
from IPython import embed
import logging
from logging import debug
from os import environ
# from http://serverfault.com/questions/71285/in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file
strip_ansi = re.compile('\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]')

#logging.basicConfig(filename='example.log',level=logging.DEBUG)

class IPythonVimApp(BaseIPythonApplication, IPythonConsoleApp):
    def initialize(self, argv):
        #IPython: why not name these differently
        # if mro is not followed anyway?
        super(IPythonVimApp, self).initialize(argv)
        IPythonConsoleApp.initialize(self, argv)

class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim
        self.vim.subscribe("ipy_connect")
        self.vim.subscribe("ipy_run")
        self.vim.subscribe("ipy_complete")
        self.vim.subscribe("ipy_objinfo")
        self.vim.subscribe("ipy_interrupt")
        self.buf = None
        self.has_connection = False
        self.pending_shell_msgs = {}

    def create_outbuf(self):
        vim = self.vim
        for b in vim.buffers:
            if "[ipython" in b.name:
                self.buf = b
                return
        w0 = vim.current.window
        vim.command(":new")
        buf = vim.current.buffer
        buf.options["buflisted"] = False
        buf.options["swapfile"] = False
        buf.options["buftype"] = "nofile"
        buf.name = "[ipython]"
        vim.current.window = w0
        self.buf = buf

    # FIXME: encoding
    def append_outbuf(self, data):
        # TODO: replace with some fancy syntax marks instead
        data = strip_ansi.sub('', data)
        lastline = self.buf[-1]

        txt = lastline + data
        self.buf[-1:] = txt.split("\n") # not splitlines
        for w in self.vim.windows:
            if w.buffer == self.buf:
                w.cursor = [len(self.buf), int(1e9)]

    def get_selection(self, kind):
        vim = self.vim
        if kind == "visual":
            b = vim.current.buffer
            start = b.mark('<')
            end = b.mark('>')
            lines = b[start[0]-1:end[0]]
            txt = '\n'.join(lines) + '\n'
            return txt
        elif kind == "line":
            return vim.current.line + '\n'
        else:
            raise ValueError("invalid object", kind)

    # TODO: perhaps expose also the "programmatic" connection api
    # TODO: should cleanly support reconnecting ( cleaning up previous connection)
    def connect(self, argv):
        if self.buf is None:
            self.create_outbuf()
        # Probably more 'idiomatic' to subclass this,
        # BUT the "fragile baseclass' problem
        self.ip_app = IPythonVimApp()
        self.ip_app.initialize(argv)
        self.kc = self.ip_app.kernel_client
        self.km = self.ip_app.kernel_manager
        self.sc = self.kc.shell_channel
        self.has_connection = True
        self.handle(self.sc.kernel_info(), self.on_kernel_info)
        # TODO: handle existing thread?
        self._ipy_thread = Thread(target=self.do_kernel_ev)
        self._ipy_thread.start()

    def on_kernel_info(self, reply):
        vim = self.vim
        c = reply['content']
        lang = c['language']
        #FIXME: (upstream) this don't seem to trigger "set ft"
        #self.buf.options['ft'] = lang
        w0 = vim.current.window
        if vim.current.buffer != self.buf:
            for w in vim.windows:
                if w.buffer == self.buf:
                    vim.current.window = w
                    break
            else:
                return #reopen window?
        vim.command("set ft={}".format(lang))
        try:
            ipy_version = c['ipython_version']
        except KeyError:
            ipy_version = IPython.version_info
        vdesc = '.'.join(str(i) for i in ipy_version[:3])
        if ipy_version[3] != '':
            vdesc += '-' + ipy_version[3]
        banner = [
                "nvim-jupyter: asynchronous interactive computing",
                "IPython {}".format(vdesc),
                "language: {} {}".format(lang, '.'.join(str(i) for i in c['language_version'])),
                "",
                ]
        self.buf[:0] = banner
        vim.current.window = w0

    def disp_status(self, status):
        self.vim.vars['ipy_status'] = status
        # TODO: how cleanly notify vimscript?
        if self.vim.eval("exists('*OnIpyStatus')"):
            self.vim.command("call OnIpyStatus()")

    #TODO: in the best of all possible worlds one should be able to integrate w/the
    # pyuv/greenlet to implement async handling of calls to other sources like IPython
    def handle(self, msg_id, handler):
        #FIXME: add timeout when refactoring event code
        self.pending_shell_msgs[msg_id] = handler

    def ignore(self, msg_id):
        self.handle(msg_id, None)

    def on_ipy_connect(self, *args):
        self.connect(args)

    def on_ipy_run(self, obj, *data):
        if not self.km.is_alive():
            choice = vim.eval("confirm('Kernel died. Restart?', '&Yes\n&No')")
            if choice == 1:
                self.km.restart_kernel(True)
            return # 
        if obj == "code":
            code, = data
        else:
            code = self.get_selection(obj)
        self.ignore(self.sc.execute(code))

    def on_ipy_complete(self):
        line = self.vim.current.line
        #FIXME: (upstream) this sometimes get wrong if 
        #completi:g just after entering insert mode:
        #pos = self.vim.current.buffer.mark(".")[1]+1
        pos = self.vim.eval("col('.')")-1
        #debug(line[:pos])
        def on_reply(reply):
            content = reply["content"]
            #TODO: check if position is still valid
            start = pos-len(content['matched_text'])+1
            matches = json.dumps(content['matches'])
            self.vim.command("call complete({}, {})".format(start,matches))
        self.handle(self.sc.complete('', line, pos), on_reply)

    def on_ipy_objinfo(self, word, level=0):
        self.handle(self.sc.object_info(word, level), self.on_objinfo_reply)

    def on_objinfo_reply(self, reply):
        c = reply['content']
        if not c['found']:
            self.append_outbuf("not found: {}\n".format(o['name']))
            return
        #TODO: enable subqueries like "what is the type", interactive argspec (like jedi-vim) etc
        self.append_outbuf("\n")
        for field in ['name','namespace','type_name','base_class','length','string_form',
            'file','definition','source','docstring']:
            if c.get(field) is None:
                continue
            sep = '\n' if c[field].count('\n') else ' '
            #TODO: option for separate doc buffer
            self.append_outbuf('{}:{}{}\n'.format(field,sep,c[field].rstrip()))

    def on_ipy_interrupt(self, msg):
        # FIXME: only works on kernel we did start
        # steal vim-ipython's getpid workaround?
        self.ip_app.kernel_manager.interrupt_kernel()


    def on_iopub_msg(self, m):
        t = m['header'].get('msg_type',None)
        c = m['content']

        if t == 'status':
            status = c['execution_state']
            self.disp_status(status)
        elif t == 'pyin':
            prompt = 'In[{}]: '.format(c['execution_count'])
            code = c['code'].rstrip().replace('\n','\n'+' '*len(prompt))
            self.append_outbuf('\n{}{}\n'.format(prompt, code))
        elif t == 'pyout':
            no = c['execution_count']
            res = c['data']['text/plain']
            self.append_outbuf('Out[{}]: {}\n'.format(no, res.rstrip()))
        elif t == 'pyerr':
            #TODO: this should be made language specific
            # as the amt of info in 'traceback' differs
            self.append_outbuf('\n'.join(c['traceback']) + '\n')
        elif t == 'stream':
            #perhaps distinguish stderr using gutter marks?
            self.append_outbuf(c['data'])
        else:
            self.append_outbuf('{!s}: {!r}\n'.format(t, c))

    def on_shell_msg(self, m):
        msg_id = m['parent_header']['msg_id']
        try:
            handler = self.pending_shell_msgs.pop(msg_id)
        except KeyError:
            debug('unexpected shell msg: %r', m)
            return
        if handler is not None:
            handler(m)

    def on_kernel_dead(self):
        self.disp_status("DEAD")

    def run(self):
        while True:
            msg = self.vim.next_message()
            kind,name,args = msg
            method = "on_" + name
            if hasattr(self, method):
                getattr(self, method)(*args)
            else:
                debug("warning: ignore %s", name)

    def do_kernel_ev(self):
        # TODO: select instead
        was_alive = True
        while True:
            is_alive = self.km.is_alive()
            if not is_alive and was_alive:
                self.vim.post("kernel_dead", [])
            was_alive = is_alive

            while self.kc.iopub_channel.msg_ready():
                msg = self.kc.iopub_channel.get_msg()
                debug(repr(msg))
                self.vim.post("iopub_msg", [msg])

            while self.sc.msg_ready():
                msg = self.sc.get_msg()
                debug(repr(msg))
                self.vim.post("shell_msg", [msg])
            sleep(0.005)

# running inside host in principle works,
# but too many a segfault :(
if False:
    class NvimIPython(IPythonPlugin):
        pass

if __name__ == "__main__":
    vim = neovim.connect(environ["NEOVIM_LISTEN_ADDRESS"])
    p = IPythonPlugin(vim)
    p.run()
