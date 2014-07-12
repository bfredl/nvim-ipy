import os, sys
import neovim
class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim
        self.create_outbuf()
        self.vim.subscribe("ipy_runline")

    def create_outbuf(self):
        vim = self.vim
        for b in vim.buffers:
            if "[ipython]" in b.name:
                self.buf = b
                return
        vim.command(":new")
        buf = vim.current.buffer
        buf.options["buflisted"] = False
        buf.options["swapfile"] = False
        buf.options["buftype"] = "nofile"
        try:
            buf.name = "[ipython]"
        except:
            #FIXME: this is not unique either
            buf.name = "[ipy-{}]".format(os.getpid())
        self.buf = buf

    def append_outbuf(self, data):
        # FIXME: encoding
        print(repr(data))
        lastline = self.buf[-1]
        txt = lastline + data
        self.buf[-1:] = txt.split("\n") # not splitlines
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

    def on_ipy_runline(self, msg):
        line = self.get_selection('line')
        self.append_outbuf(line)

    def do_ev(self,timeout=None):
        try:
            msg = self.vim.next_message(timeout)
        except NameError: #FIXME: upstream should emit TimeoutError
            return 0
        method = "on_" + msg.name
        if hasattr(self, method):
            getattr(self, method)(msg)
        else:
            print("warning: ignore", msg.name)
        return 0 #inputhook shall return 0

    def run(self):
        while True: self.do_ev()

    # debug ipython client plugint using ipython console...
    def ipython_inputhook_register(self):
        from IPython.lib.inputhook import inputhook_manager
        inputhook_manager.set_inputhook(lambda: self.do_ev(0))
        
def test_ipython(path):
    vim = neovim.connect(path)
    p = IPythonPlugin(vim)
    p.ipython_inputhook_register()
    return vim, p

if __name__ == "__main__":
    vim = neovim.connect(sys.argv[1])
    IPythonPlugin(vim).run()

        
