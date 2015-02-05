This is a IPython client for Neovim, based on ivanov/vim-ipython, but refactored for nvim's plugin architechture and improved async event handling. It supports IPython 2.x and 3.x (as of 3.0-beta1).

It is not as feature-complete as vim-ipython, but it has better support for long-running commands that continously produce output, for instance this silly example:

    from time import sleep
    for i in range(10):
        sleep(0.5)
        print(i)

Another difference, `:IPython <args>` is interpreted the same as the command line `ipython console <args>`, for instance:

Start new python kernel: (on IPython2.x, python3 is supported through a hack that assumes `python3` is in $PATH )

    :IPython
    :IPython3
Connect to existing kernel:

    :IPython --existing
Start kernel in different language (if installed). 

    :IPython --profile julia
    :IPython --profile haskell
this will be better supported in IPython 3.x (Jupyter)

See plugin/ipy.vim for keybindings (you might want to override these)
