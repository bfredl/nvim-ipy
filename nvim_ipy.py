from __future__ import print_function, division
import os, sys
import neovim
import IPython
from IPython.kernel import KernelManager, find_connection_file
class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim
        self.create_outbuf()
        self.vim.subscribe("ipy_runline")
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

    def append_outbuf(self, data):
        # FIXME: encoding
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

    # TODO: subclass IPythonConsoleApp for flexibe launch/reconnetion to kernels
    # only support connect to exisitng for now
    def connect(self, path, profile=None):
        fullpath = find_connection_file(path)
        self.km = KernelManager(connection_file = fullpath)
        self.km.load_connection_file()
        self.kc = self.km.client()
        self.kc.start_channels()
        self.sc = self.kc.shell_channel
        self.has_connection = True

        self.handle(self.sc.kernel_info(), self.on_kernel_info)

    def on_kernel_info(self, reply):
        lang = reply['content']['language']
        #FIXME: (upstream) this don't seem to trigger "set ft"
        self.buf.options['ft'] = lang

    def handle(self, msg_id, handler):
        self.pending_shell_msgs[msg_id] = handler

    def ignore(self, msg_id):
        self.handle(msg_id, None)

    def on_ipy_runline(self, msg):
        line = self.get_selection('line')
        self.ignore(self.sc.execute(line))

    def on_iopub_msg(self, m):
        t = m['header'].get('msg_type',None)
        content = m['content']

        if t == 'status':
            status = content['execution_state']
            if status == 'busy':
                #FIXME: export a hook for airline etc instead
                self.buf.name = '[ipython-busy]'
            else:
                self.buf.name = '[ipython]'
        elif t == 'pyin':
            no = content['execution_count']
            code = content['code']
            self.append_outbuf('In[{}]: {}\n'.format(no, code.rstrip()))
        elif t == 'pyout':
            no = content['execution_count']
            res = content['data']['text/plain']
            self.append_outbuf('Out[{}]: {}\n\n'.format(no, res.rstrip()))
        else:
            self.append_outbuf('{!s}: {!r}\n'.format(t, content))

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
        while True: #FIXME: select instead
            self.do_ev()
            sleep(0.005)

    # debug ipython client plugint using ipython console...
    def ipython_inputhook_register(self):
        from IPython.lib.inputhook import inputhook_manager
        inputhook_manager.set_inputhook(lambda: self.do_ev())
        
def test_ipython(nvpath, ippath):
    vim = neovim.connect(nvpath)
    p = IPythonPlugin(vim)
    p.ipython_inputhook_register()
    p.connect(ippath)
    return vim, p

if __name__ == "__main__":
    vim = neovim.connect(sys.argv[1])
    IPythonPlugin(vim).run()

        
