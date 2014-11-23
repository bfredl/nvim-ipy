This is a IPython client for Neovim, based on ivanov/vim-ipython, but refactored for nvim's plugin architechture and improved async event handling. It is not as feature complete as vim-ipython, but it has better support for long-running commands that continously produce output, for instance this silly example:

    from time import sleep
    for i in range(10):
        sleep(0.5)
        print(i)

Another difference, `:IPython <args>` is interpreted the same as the command line `ipython console <args>`, for instance:

Start new python kernel:

    :IPython
Connect to existing kernel:

    :IPython --existing
Start kernel in diffenent language (if installed)

    :IPython -profile julia
    :IPython -profile haskell
(this might be more flexibe in IPython 3.0)

See plugin/ipy.vim for keybindings (you might want to overide these)
