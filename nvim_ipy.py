import os
import neovim
class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim

    def create_outbuf(self):
        vim = self.vim
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
        lastline = self.buf[-1]
        txt = lastline + data
        self.buf[-1:] = txt.splitlines()

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


        
