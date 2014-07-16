from __future__ import print_function, division
from time import sleep
import os, sys
import json
import re
import neovim
import IPython
from IPython.kernel import KernelManager, find_connection_file
from IPython.core.application import BaseIPythonApplication
from IPython.consoleapp import IPythonConsoleApp

# from http://serverfault.com/questions/71285/in-centos-4-4-how-can-i-strip-escape-sequences-from-a-text-file
strip_ansi = re.compile('\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]')

class IPythonVimApp(IPythonConsoleApp, BaseIPythonApplication):
    def initialize(self, argv):
        #TODO: find out the proper way of doing this
        BaseIPythonApplication.initialize(self, argv)
        IPythonConsoleApp.initialize(self, argv)

class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim
        self.create_outbuf()
        self.vim.subscribe("ipy_run")
        self.vim.subscribe("ipy_complete")
        self.vim.subscribe("ipy_objinfo")
        self.vim.subscribe("ipy_interrupt")
        self.has_connection = False
        self.pending_shell_msgs = {}

    def create_outbuf(self):
        vim = self.vim
        for b in vim.buffers:
            if "[ipython" in b.name:
                self.buf = b
                return
        vim.command(":new")
        buf = vim.current.buffer
        buf.options["buflisted"] = False
        buf.options["swapfile"] = False
        buf.options["buftype"] = "nofile"
        buf.name = "[ipython]"
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
                w0 = self.vim.current.window
                #FIXME: (upstream) cursor pos is only updated in current window!
                self.vim.current.window = w
                w.cursor = [len(self.buf), int(1e9)]
                self.vim.current.window = w0


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

    # TODO: perhaps expose also the "programmatic" connection api
    def connect(self, argv):
        # Probably more 'idiomatic' to subclass this,
        # BUT the "fragile baseclass' problem
        self.ip_app = IPythonVimApp()
        self.ip_app.initialize(argv)
        self.kc = self.ip_app.kernel_client
        self.sc = self.kc.shell_channel
        self.has_connection = True

        self.handle(self.sc.kernel_info(), self.on_kernel_info)

    def on_kernel_info(self, reply):
        c = reply['content']
        lang = c['language']
        #FIXME: (upstream) this don't seem to trigger "set ft"
        #self.buf.options['ft'] = lang
        w0 = self.vim.current.window
        if self.vim.current.buffer != self.buf:
            for w in self.vim.windows:
                if w.buffer == self.buf:
                    self.vim.current.window = w
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
        self.vim.current.window = w0



    def handle(self, msg_id, handler):
        #FIXME: add timeout when refactoring event code
        self.pending_shell_msgs[msg_id] = handler

    def ignore(self, msg_id):
        self.handle(msg_id, None)

    def on_ipy_run(self, msg):
        sel = self.get_selection(msg.arg[0])
        self.ignore(self.sc.execute(sel))

    def on_ipy_complete(self, msg):
        line = self.vim.current.line
        #FIXME: (upstream) this sometimes get wrong if 
        #completi:g just after entering insert mode:
        #pos = self.vim.current.buffer.mark(".")[1]+1
        pos = self.vim.eval("col('.')")-1
        print(line[:pos])
        def on_reply(reply):
            content = reply["content"]
            #TODO: check if position is still valid
            start = pos-len(content['matched_text'])+1
            matches = json.dumps(content['matches'])
            self.vim.send_command("call complete({}, {})".format(start,matches))
        self.handle(self.sc.complete('', line, pos), on_reply)

    def on_ipy_objinfo(self, msg):
        word = msg.arg[0]
        try:
            level = msg.arg[1]
        except IndexError:
            level = 0
        self.handle(self.sc.object_info(word, level), self.on_objinfo_reply)

    def on_objinfo_reply(self, reply):
        c = reply['content']
        if not c['found']:
            self.append_outbuf("not found: {}\n".format(o['name']))
            return
        #TODO: enable subqueries like "what is the type", interactive argspec (like jedi-vim) etc
        for field in ['name','namespace','type_name','base_class','length','string_form',
            'file','definition','source','docstring']:
            if field not in c:
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
            if status == 'busy':
                #FIXME: export a hook for airline etc instead
                self.buf.name = '[ipython-busy]'
            else:
                self.buf.name = '[ipython]'
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
            print('unexpected shell msg:', repr(m))
            return
        if handler is not None:
            handler(m)

    def do_nvim_ev(self,timeout=None):
        try:
            msg = self.vim.next_message(timeout)
        except NameError: #FIXME: upstream should emit TimeoutError
            return
        method = "on_" + msg.name
        if hasattr(self, method):
            getattr(self, method)(msg)
        else:
            print("warning: ignore", msg.name)
        return 0 #inputhook shall return 0

    def do_kernel_ev(self):
        while self.kc.iopub_channel.msg_ready():
            msg = self.kc.iopub_channel.get_msg()
            self.on_iopub_msg(msg)

        while self.sc.msg_ready():
            msg = self.sc.get_msg()
            self.on_shell_msg(msg)

    def do_ev(self):
        self.do_nvim_ev(0)
        if self.has_connection: self.do_kernel_ev()
        return 0

    def run(self):
        while True: #FIXME: use push_message instead
            self.do_ev()
            sleep(0.005)

    # debug ipython client plugint using ipython console...
    def ipython_inputhook_register(self):
        from IPython.lib.inputhook import inputhook_manager
        inputhook_manager.set_inputhook(lambda: self.do_ev())
        
def test_ipython(nvpath, argv):
    vim = neovim.connect(nvpath)
    p = IPythonPlugin(vim)
    p.ipython_inputhook_register()
    p.connect(argv)
    return vim, p

if __name__ == "__main__":
    vim = neovim.connect(sys.argv[1])
    p = IPythonPlugin(vim)
    p.connect(sys.argv[2:])
    p.run()
