command! -nargs=* IPython :call IPyConnect(<f-args>)
command! -nargs=* IJulia :call IPyConnect("--profile", "julia")

nnoremap <Plug>(IPy-RunLine) :call IPyRunSelection('line')<cr>
vnoremap <Plug>(IPy-RunLine) :<c-u>call IPyRunSelection('vline')<cr>
inoremap <Plug>(IPy-Complete) <c-o>:<c-u>call IPyComplete()<cr>
noremap <Plug>(IPy-Interrupt) :call IPyInterrupt()<cr>


function! IPyWordObjinfo()
    let isk_save = &isk
    let &isk = '@,48-57,_,192-255,.'
    let word = expand("<cword>")
    let &isk = isk_save
    call IPyObjInfo(word, 0)
endfunction

if !exists('g:nvim_ipy_perform_mappings')
    let g:nvim_ipy_perform_mappings = 1
endif

let g:ipy_status = ""

if g:nvim_ipy_perform_mappings
    map <silent> <F5>           <Plug>(IPy-RunLine)
    imap <silent> <C-Space> <Plug>(IPy-Complete)
    map <silent> <F8> <Plug>(IPy-Interrupt)
    map <silent> <Leader>d :call IPyWordObjinfo()
    set titlestring=%t%(\ %M%)%(\ (%{expand(\"%:p:h\")})%)%(\ %a%)%(\ -\ %{g:ipy_status}%)
endif


